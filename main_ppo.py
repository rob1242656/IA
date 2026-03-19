import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pymunk
import pymunk.pygame_util
import pygame
import multiprocessing
import os

from stable_baselines3 import SAC
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor, VecNormalize
from stable_baselines3.common.callbacks import CheckpointCallback

# --- CONSTANTES ---
COLL_SUELO = 1
COLL_OBSTACULO = 2
COLL_TORSO = 10
COLL_PIE_IZQ = 11
COLL_PIE_DER = 12
COLL_MUSLO = 13

# Configuración
ANCHO, ALTO = 1000, 600
# Nombre del modelo NUEVO que vamos a guardar
NOMBRE_NUEVO = "sonso_v12b_gait_fixed"

class SonsoEnv(gym.Env):
    metadata = {'render_modes': ['human'], 'render_fps': 60}

    def __init__(self, render_mode=None):
        super(SonsoEnv, self).__init__()
        self.render_mode = render_mode
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(30,), dtype=np.float32)
        
        # Variables Manager
        self.goal_velocity = 0.0
        self.dist_lidar_lejos = 1.0
        
        # Variables Física (Se sobrescriben en reset)
        self.grav_y = 900.0
        self.friccion_dr = 1.0
        
        if self.render_mode == 'human':
            pygame.init()
            pygame.font.init()
            self.screen = pygame.display.set_mode((ANCHO, ALTO))
            pygame.display.set_caption(f"Sonso IA: V12 (Gait)")
            self.clock = pygame.time.Clock()
            self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)
            self.font = pygame.font.SysFont("Consolas", 18)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.space = pymunk.Space()
        
        # --- V11: CURRICULUM DR (Perturbaciones Suaves) ---
        # Ya no es fijo (900), pero tampoco es caos (700-1100).
        # Es una variación del +/- 5% para "robustecer" la caminata.
        self.grav_y = np.random.uniform(850.0, 950.0) 
        self.space.gravity = (0.0, self.grav_y)
        
        # Suelos ligeramente distintos (Goma vs Tierra)
        self.friccion_dr = np.random.uniform(0.8, 1.2)
        
        self.c_izq_counter = 0; self.c_der_counter = 0
        self.prev_contact_izq = False; self.prev_contact_der = False
        self.impacto_izq = 0.0; self.impacto_der = 0.0
        self.impacto_torso = 0.0; self.impacto_muslo = 0.0
        
        self.tiempo = 0
        self.prev_action = np.zeros(4)
        self.push_visual = 0
        self.lista_obstaculos = []
        self.obstaculos_info = []   # guarda {body, w, h} para exportar a Blender

        # Tracking de marcha (v12)
        self.last_step_izq = 0
        self.last_step_der = 0
        self.last_foot_down = 0   # 0=ninguno, 1=izq, 2=der
        self.airtime_counter = 0
        self.prev_pos_x = 200.0

        self.goal_velocity = 0.0; self.dist_lidar_lejos = 1.0
        
        self._crear_escenario()
        self._crear_robot(200, 420) 
        self.next_obstacle_x = 1000 
        
        return self._get_obs(), {}

    # --- DETECCIÓN DE CONTACTOS GEOMÉTRICA (sin API de colisiones pymunk) ---
    def _detectar_contactos(self):
        """
        Detección geométrica AABB — compatible con cualquier versión de pymunk.
        No usa add_collision_handler ni space.arbiters.
        """
        GROUND_Y = 544.0   # suelo está en y=550 con 5px grosor → toca en ~544
        MARGIN   = 4.0

        def toca_entorno(cuerpo, medio_w, medio_h):
            bx, by = cuerpo.position.x, cuerpo.position.y
            # Suelo plano
            if by + medio_h + MARGIN >= GROUND_Y:
                return True
            # Obstáculos (AABB con dimensiones correctas de cada parte)
            for info in self.obstaculos_info:
                ox, oy = info['body'].position.x, info['body'].position.y
                if (abs(bx - ox) < medio_w + MARGIN + info['w'] / 2 and
                        abs(by - oy) < medio_h + MARGIN + info['h'] / 2):
                    return True
            return False

        self.c_izq_counter = 0;  self.c_der_counter = 0
        self.impacto_izq   = 0.0; self.impacto_der   = 0.0
        self.impacto_torso = 0.0; self.impacto_muslo = 0.0

        # Pies (caja 10×45 → half_w=5, half_h=22.5)
        if toca_entorno(self.pierna_izq['pie'], 5.0, 22.5):
            self.c_izq_counter = 1
            self.impacto_izq = self.pierna_izq['pie'].velocity.length * 50.0
        if toca_entorno(self.pierna_der['pie'], 5.0, 22.5):
            self.c_der_counter = 1
            self.impacto_der = self.pierna_der['pie'].velocity.length * 50.0

        # Muslos (caja 12×45 → half_w=6, half_h=22.5)
        if (toca_entorno(self.pierna_izq['muslo_body'], 6.0, 22.5) or
                toca_entorno(self.pierna_der['muslo_body'], 6.0, 22.5)):
            self.impacto_muslo = 25.0   # supera umbral 20 → termina

        # Torso (caja 40×60 → half_w=20, half_h=30)
        if toca_entorno(self.torso_body, 20.0, 30.0):
            self.impacto_torso = 250.0  # supera umbral 200 → termina

    # --- MANAGER V12 (Transición Suave) ---
    def _actualizar_manager(self):
        target_vel = 2.0 if self.dist_lidar_lejos < 0.4 else 5.0  # v12b: meta reducida para aprendizaje
        SMOOTH_RATE = 0.3
        if self.goal_velocity < target_vel:
            self.goal_velocity = min(self.goal_velocity + SMOOTH_RATE, target_vel)
        else:
            self.goal_velocity = max(self.goal_velocity - SMOOTH_RATE, target_vel)

    def step(self, action):
        self.tiempo += 1

        # PUSH desactivado en v12b (robot aprende desde cero, push mortal para principiante)
        # Reactivar en v13 cuando ep_len > 800 consistentemente
        self.push_visual = 0

        if self.torso_body.position.x > self.next_obstacle_x - 700:
            self._generar_obstaculo(self.next_obstacle_x)
            self.next_obstacle_x += np.random.randint(500, 1000) 

        for obs in self.lista_obstaculos[:]:
            if obs.position.x < self.torso_body.position.x - 1500:
                self.space.remove(obs, *obs.shapes)
                self.lista_obstaculos.remove(obs)
                self.obstaculos_info = [i for i in self.obstaculos_info if i["body"] is not obs]

        action = np.clip(action, -1.0, 1.0)
        alpha = 0.6
        smoothed_action = (1 - alpha) * self.prev_action + alpha * action
        
        v_max = 9.0 
        motores = [self.pierna_izq['m_cadera'], self.pierna_izq['m_rodilla'],
                   self.pierna_der['m_cadera'], self.pierna_der['m_rodilla']]
        for i, m in enumerate(motores): m.rate = float(smoothed_action[i]) * v_max

        for _ in range(4): self.space.step(1.0 / 240.0)
        self._detectar_contactos()

        if self.tiempo % 30 == 0: self._actualizar_manager()

        # REWARD V12
        vel_x = self.torso_body.velocity.x
        angle = self.torso_body.angle
        pos_y = self.torso_body.position.y
        pos_x = self.torso_body.position.x
        is_contact_izq = self.c_izq_counter > 0
        is_contact_der = self.c_der_counter > 0
        both_in_air = not is_contact_izq and not is_contact_der

        reward = 0.0

        # A. Velocidad
        vel_error = abs(vel_x - self.goal_velocity)
        if vel_x >= 0.0:
            # Gaussiana ancha: da gradiente aunque el robot vaya lento
            reward += 1.5 * np.exp(-0.08 * vel_error)
            reward += 0.3 * float(vel_x) / 5.0          # bonus lineal por avanzar (max goal=5)
        else:
            # Ir hacia atrás = penalización clara (sin reward positivo por gaussiana)
            reward -= 0.5 + abs(float(vel_x)) * 0.05

        # B. Postura suave
        reward += 0.8 * np.exp(-2.0 * angle**2)
        reward += 0.4 * np.exp(-0.005 * (pos_y - 460.0)**2)
        reward -= abs(angle) * 0.3

        # C. Marcha alternada
        new_contact_izq = is_contact_izq and not self.prev_contact_izq
        new_contact_der = is_contact_der and not self.prev_contact_der

        if new_contact_izq:
            self.last_step_izq = self.tiempo
            if self.last_foot_down == 2:   reward += 2.0   # alternancia correcta
            elif self.last_foot_down == 1: reward -= 0.5   # mismo pie = cojeo
            else:                          reward += 0.5   # primer paso
            self.last_foot_down = 1

        if new_contact_der:
            self.last_step_der = self.tiempo
            if self.last_foot_down == 1:   reward += 2.0
            elif self.last_foot_down == 2: reward -= 0.5
            else:                          reward += 0.5
            self.last_foot_down = 2

        # Penalizar hopping (ambos pies en el aire >8 steps)
        if both_in_air:
            self.airtime_counter += 1
            if self.airtime_counter > 8:
                reward -= 0.3
        else:
            self.airtime_counter = 0

        # Recompensar cadencia rítmica (20-80 steps entre pasos)
        if new_contact_izq and self.last_step_der > 0:
            if 20 <= (self.tiempo - self.last_step_der) <= 80:
                reward += 0.5
        elif new_contact_der and self.last_step_izq > 0:
            if 20 <= (self.tiempo - self.last_step_izq) <= 80:
                reward += 0.5

        # D. Energía (aumentada + jerk penalty)
        reward -= np.sum(np.square(smoothed_action)) * 0.02
        reward -= np.sum(np.square(smoothed_action - self.prev_action)) * 0.01

        # E. Seguridad
        terminated = False
        if self.impacto_torso > 200:    reward -= 5.0;  terminated = True
        if self.impacto_muslo > 20.0:   reward -= 20.0; terminated = True
        pie_impact = self.impacto_izq + self.impacto_der
        if pie_impact > 3000:
            reward -= (pie_impact - 3000) / 2000.0
        if pos_y > 520 or abs(angle) > 1.2:
            reward -= 10.0; terminated = True

        # Actualizar estado
        self.prev_contact_izq = is_contact_izq
        self.prev_contact_der = is_contact_der
        self.prev_pos_x = pos_x
        self.prev_action = smoothed_action

        truncated = False
        if self.tiempo > 2000: truncated = True

        if self.render_mode == "human": self._render_frame()
        return self._get_obs(), reward, terminated, truncated, {}

    def _get_obs(self):
        rb = self.torso_body
        d_suelo, n_suelo_x, n_suelo_y = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(0, 150), stabilized=False)
        d_lejos, _, _ = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(700, 80), stabilized=True)
        d_salto, _, _ = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(150, 60), stabilized=False)
        self.dist_lidar_lejos = d_lejos 

        ang_muslo_izq = self.pierna_izq['muslo_body'].angle - rb.angle
        ang_rodilla_izq = self.pierna_izq['pie'].angle - self.pierna_izq['muslo_body'].angle
        ang_muslo_der = self.pierna_der['muslo_body'].angle - rb.angle
        ang_rodilla_der = self.pierna_der['pie'].angle - self.pierna_der['muslo_body'].angle

        imp_muslo_norm = min(self.impacto_muslo / 5000.0, 1.0)
        imp_torso_norm = min(self.impacto_torso / 5000.0, 1.0)
        meta_norm = self.goal_velocity / 5.0   # max goal_velocity en v12b es 5.0

        obs = [
            (rb.position.y - 450.0) / 100.0, np.sin(rb.angle), np.cos(rb.angle), 
            rb.velocity.x / 100.0, rb.velocity.y / 100.0,
            self.pierna_izq['m_cadera'].rate / 9.0, self.pierna_izq['m_rodilla'].rate / 9.0,
            self.pierna_der['m_cadera'].rate / 9.0, self.pierna_der['m_rodilla'].rate / 9.0,
            1.0 if self.c_izq_counter > 0 else 0.0, 1.0 if self.c_der_counter > 0 else 0.0,
            d_suelo, n_suelo_x, n_suelo_y, d_lejos, d_salto, 
            self.impacto_izq/5000.0, self.impacto_der/5000.0,
            ang_muslo_izq, ang_rodilla_izq, ang_muslo_der, ang_rodilla_der,
            self.prev_action[0], self.prev_action[1], self.prev_action[2], self.prev_action[3],
            self.grav_y / 1000.0, imp_muslo_norm, imp_torso_norm, meta_norm 
        ]
        return np.array(obs, dtype=np.float32)

    def _raycast(self, start, end, stabilized=False):
        p_start = self.torso_body.position + start.rotated(self.torso_body.angle)
        if stabilized: p_end = self.torso_body.position + end
        else: p_end = self.torso_body.position + end.rotated(self.torso_body.angle)
        f = pymunk.ShapeFilter(mask=pymunk.ShapeFilter.ALL_MASKS() ^ 2) 
        res = self.space.segment_query_first(p_start, p_end, 1, f)
        if res: return res.alpha, res.normal.x, res.normal.y 
        return 1.0, 0.0, -1.0 

    def _crear_escenario(self):
        suelo = pymunk.Segment(self.space.static_body, (-2000, 550), (500000, 550), 5.0)
        suelo.friction = 1.0; suelo.collision_type = COLL_SUELO 
        self.space.add(suelo)

    def _crear_robot(self, x, y):
        masa = 8.0 
        self.torso_body = pymunk.Body(masa, pymunk.moment_for_box(masa, (40, 60)))
        self.torso_body.position = (x, y)
        shape = pymunk.Poly.create_box(self.torso_body, (40, 60))
        shape.filter = pymunk.ShapeFilter(group=2, categories=2) 
        shape.friction = 0.5
        shape.collision_type = COLL_TORSO 
        self.space.add(self.torso_body, shape)
        self.pierna_izq = self._crear_pierna(x, y+30, COLL_PIE_IZQ, self.friccion_dr) 
        self.pierna_der = self._crear_pierna(x, y+30, COLL_PIE_DER, self.friccion_dr) 

    def _crear_pierna(self, x, y, c_type_pie, friccion):
        m_muslo = 2.0; muslo = pymunk.Body(m_muslo, pymunk.moment_for_box(m_muslo, (12, 45)))
        muslo.position = (x, y + 25)
        m_shape = pymunk.Poly.create_box(muslo, (12, 45))
        m_shape.filter = pymunk.ShapeFilter(group=2, categories=2)
        m_shape.collision_type = COLL_MUSLO 
        m_shape.friction = friccion 
        pivot = pymunk.PivotJoint(self.torso_body, muslo, (0, 25), (0, -20))
        motor = pymunk.SimpleMotor(self.torso_body, muslo, 0)
        motor.max_force = 100000 
        limite = pymunk.RotaryLimitJoint(self.torso_body, muslo, -1.2, 0.4)
        self.space.add(muslo, m_shape, pivot, motor, limite)
        panto = pymunk.Body(1.0, pymunk.moment_for_box(1.0, (10, 45)))
        panto.position = (x, y + 65)
        p_shape = pymunk.Poly.create_box(panto, (10, 45))
        p_shape.filter = pymunk.ShapeFilter(group=2, categories=2)
        p_shape.friction = friccion 
        p_shape.collision_type = c_type_pie 
        pivot_r = pymunk.PivotJoint(muslo, panto, (0, 20), (0, -20))
        motor_r = pymunk.SimpleMotor(muslo, panto, 0)
        motor_r.max_force = 100000 
        limite_r = pymunk.RotaryLimitJoint(muslo, panto, 0.0, 2.2) 
        self.space.add(panto, p_shape, pivot_r, motor_r, limite_r)
        return {'m_cadera': motor, 'm_rodilla': motor_r, 'muslo_body': muslo, 'pie': panto}

    def _generar_obstaculo(self, x):
        h = np.random.randint(20, 45); w = np.random.randint(30, 60)
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = (x, 550 - (h/2))
        shape = pymunk.Poly.create_box(body, (w, h))
        shape.friction = 1.5 
        shape.collision_type = COLL_OBSTACULO; shape.color = (200, 50, 50, 255)
        self.space.add(body, shape)
        self.lista_obstaculos.append(body)
        self.obstaculos_info.append({"body": body, "w": w, "h": h})

    def _render_frame(self):
        offset_x = -self.torso_body.position.x + 300
        self.draw_options.transform = pymunk.Transform.translation(offset_x, 0)
        self.screen.fill((240, 240, 240))
        self.space.debug_draw(self.draw_options)
        
        st = self.torso_body.position; end = st + pymunk.Vec2d(700, 80) 
        st_scr = st + pymunk.Vec2d(offset_x, 0); end_scr = end + pymunk.Vec2d(offset_x, 0)
        try: pygame.draw.line(self.screen, (0, 255, 0), (st_scr.x, st_scr.y), (end_scr.x, end_scr.y), 2)
        except: pass

        txt_vel = self.font.render(f"Vel: {self.torso_body.velocity.x:.1f} | META: {self.goal_velocity:.1f}", True, (50, 50, 50))
        self.screen.blit(txt_vel, (20, 20))
        txt_grav = self.font.render(f"Grav: {self.grav_y:.0f} | Fric: {self.friccion_dr:.1f}", True, (50, 50, 50))
        self.screen.blit(txt_grav, (20, 45))
        pygame.display.flip(); self.clock.tick(60)

    def get_render_data(self):
        """Posiciones y ángulos mundiales de cada parte del robot (coordenadas Pymunk)."""
        return {
            "torso":     {"x": self.torso_body.position.x,
                          "y": self.torso_body.position.y,
                          "angle": self.torso_body.angle},
            "muslo_izq": {"x": self.pierna_izq['muslo_body'].position.x,
                          "y": self.pierna_izq['muslo_body'].position.y,
                          "angle": self.pierna_izq['muslo_body'].angle},
            "muslo_der": {"x": self.pierna_der['muslo_body'].position.x,
                          "y": self.pierna_der['muslo_body'].position.y,
                          "angle": self.pierna_der['muslo_body'].angle},
            "pie_izq":   {"x": self.pierna_izq['pie'].position.x,
                          "y": self.pierna_izq['pie'].position.y,
                          "angle": self.pierna_izq['pie'].angle},
            "pie_der":   {"x": self.pierna_der['pie'].position.x,
                          "y": self.pierna_der['pie'].position.y,
                          "angle": self.pierna_der['pie'].angle},
            "obstacles": [{"x": i["body"].position.x, "y": i["body"].position.y,
                           "w": i["w"], "h": i["h"]}
                          for i in self.obstaculos_info],
        }

# ==========================================
# TRAINING: CONTINUACIÓN Y EXPANSIÓN
# ==========================================
def make_env(): return SonsoEnv(render_mode=None)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    os.makedirs("logs", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    print("="*60)
    print(f"🦿 SONSO IA: V12.0 {NOMBRE_NUEVO} (GAIT) — DESDE CERO")
    print("   -> Estrategia: Gait Alternado + Manager Suave")
    print("="*60)

    n_procs = 4
    env = SubprocVecEnv([make_env for _ in range(n_procs)])
    env = VecMonitor(env, filename=f"logs/{NOMBRE_NUEVO}")
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=0.99)

    model = SAC(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        batch_size=512,
        buffer_size=1_000_000,
        learning_starts=10_000,
        gamma=0.99,
        tau=0.005,
        ent_coef=0.1,   # fijo: fuerza exploración constante, evita colapso determinístico
        tensorboard_log="./tensorboard/",
    )
    print("✅ Modelo nuevo creado desde cero.")

    checkpoint_callback = CheckpointCallback(
        save_freq=50_000,
        save_path=f"./models/{NOMBRE_NUEVO}/",
        name_prefix=NOMBRE_NUEVO,
    )

    print(">> INICIANDO ENTRENAMIENTO (4M Steps)...")
    try:
        model.learn(total_timesteps=4_000_000, callback=checkpoint_callback, log_interval=4)
        model.save(NOMBRE_NUEVO)
        env.save(f"{NOMBRE_NUEVO}_vecnorm.pkl")
        print(">> ENTRENAMIENTO FINALIZADO.")
    except KeyboardInterrupt:
        model.save(NOMBRE_NUEVO)
        env.save(f"{NOMBRE_NUEVO}_vecnorm.pkl")
        print(">> Guardado por interrupción.")
    finally:
        env.close()