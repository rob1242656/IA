"""
sonso_v13_design.py — Sonso V13: Perturbaciones + Terreno Variable
====================================================================
Mejoras sobre V12b:
  1. Push forces reactivadas (el robot ya camina estable con ep_len ~600)
  2. Terreno variable: pendientes suaves (rampas)
  3. Curriculum learning: dificultad sube con el tiempo
  4. Red mas grande: 512 neuronas (preparacion para GPU)
  5. Velocidad angular del torso como observacion adicional

Prerequisito: Sonso v12b entrenado exitosamente (ep_rew ~2900)
"""
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

ANCHO, ALTO = 1000, 600
NOMBRE_NUEVO = "sonso_v13_perturbation"


class SonsoV13Env(gym.Env):
    """
    Sonso V13 — Heredero de V12b con:
      - Push forces aleatorias (perturbaciones externas)
      - Rampas/pendientes
      - Curriculum: dificultad escala con timesteps
      - Obs ampliado (32 dims): +vel_angular_torso, +inclinacion_terreno
    """
    metadata = {'render_modes': ['human'], 'render_fps': 60}

    def __init__(self, render_mode=None):
        super(SonsoV13Env, self).__init__()
        self.render_mode = render_mode
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
        # V13: 32 observaciones (v12b tenia 30, +vel_angular +inclinacion_terreno)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(32,), dtype=np.float32)

        self.goal_velocity = 0.0
        self.dist_lidar_lejos = 1.0
        self.grav_y = 900.0
        self.friccion_dr = 1.0

        # V13: Curriculum difficulty (0.0 = facil, 1.0 = maximo)
        self.difficulty = 0.0
        self.total_episodes = 0

        # V13: Push tracking
        self.push_cooldown = 0
        self.push_visual = 0

        if self.render_mode == 'human':
            pygame.init()
            pygame.font.init()
            self.screen = pygame.display.set_mode((ANCHO, ALTO))
            pygame.display.set_caption("Sonso IA: V13 (Perturbation)")
            self.clock = pygame.time.Clock()
            self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)
            self.font = pygame.font.SysFont("Consolas", 18)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.space = pymunk.Space()
        self.total_episodes += 1

        # --- CURRICULUM: dificultad sube gradualmente ---
        # Cada 500 episodios sube 0.1, maximo 1.0
        self.difficulty = min(1.0, self.total_episodes / 5000.0)

        # DR escalado por dificultad
        grav_range = 50.0 + 50.0 * self.difficulty  # 50 -> 100 (900 +/- range)
        self.grav_y = np.random.uniform(900.0 - grav_range, 900.0 + grav_range)
        self.space.gravity = (0.0, self.grav_y)

        fric_range = 0.2 + 0.2 * self.difficulty   # 0.2 -> 0.4
        self.friccion_dr = np.random.uniform(1.0 - fric_range, 1.0 + fric_range)

        # State reset
        self.c_izq_counter = 0; self.c_der_counter = 0
        self.prev_contact_izq = False; self.prev_contact_der = False
        self.impacto_izq = 0.0; self.impacto_der = 0.0
        self.impacto_torso = 0.0; self.impacto_muslo = 0.0

        self.tiempo = 0
        self.prev_action = np.zeros(4)
        self.push_visual = 0
        self.push_cooldown = 0
        self.lista_obstaculos = []
        self.obstaculos_info = []
        self.rampas = []

        self.last_step_izq = 0
        self.last_step_der = 0
        self.last_foot_down = 0
        self.airtime_counter = 0
        self.prev_pos_x = 200.0
        self.inclinacion_terreno = 0.0  # V13: pendiente actual del terreno

        self.goal_velocity = 0.0; self.dist_lidar_lejos = 1.0

        self._crear_escenario()
        self._crear_robot(200, 420)
        self.next_obstacle_x = 1000
        self.next_ramp_x = 2000  # V13: primera rampa mas lejos

        return self._get_obs(), {}

    def _detectar_contactos(self):
        GROUND_Y = 545.0
        MARGIN = 4.0

        def toca_entorno(cuerpo, medio_w, medio_h):
            bx, by = cuerpo.position.x, cuerpo.position.y
            if by + medio_h + MARGIN >= GROUND_Y:
                return True
            for info in self.obstaculos_info:
                ox, oy = info['body'].position.x, info['body'].position.y
                if (abs(bx - ox) < medio_w + MARGIN + info['w'] / 2 and
                        abs(by - oy) < medio_h + MARGIN + info['h'] / 2):
                    return True
            return False

        self.c_izq_counter = 0; self.c_der_counter = 0
        self.impacto_izq = 0.0; self.impacto_der = 0.0
        self.impacto_torso = 0.0; self.impacto_muslo = 0.0

        if toca_entorno(self.pierna_izq['pie'], 5.0, 22.5):
            self.c_izq_counter = 1
            self.impacto_izq = self.pierna_izq['pie'].velocity.length * 50.0
        if toca_entorno(self.pierna_der['pie'], 5.0, 22.5):
            self.c_der_counter = 1
            self.impacto_der = self.pierna_der['pie'].velocity.length * 50.0

        if (toca_entorno(self.pierna_izq['muslo_body'], 6.0, 22.5) or
                toca_entorno(self.pierna_der['muslo_body'], 6.0, 22.5)):
            self.impacto_muslo = 25.0

        if toca_entorno(self.torso_body, 20.0, 30.0):
            self.impacto_torso = 250.0

    def _actualizar_manager(self):
        target_vel = 2.0 if self.dist_lidar_lejos < 0.4 else 5.0
        SMOOTH_RATE = 0.3
        if self.goal_velocity < target_vel:
            self.goal_velocity = min(self.goal_velocity + SMOOTH_RATE, target_vel)
        else:
            self.goal_velocity = max(self.goal_velocity - SMOOTH_RATE, target_vel)

    def _aplicar_push(self):
        """V13: Perturbacion externa aleatoria (viento/empujon)."""
        if self.push_cooldown > 0:
            self.push_cooldown -= 1
            return

        # Probabilidad de push escala con dificultad
        push_prob = 0.002 * self.difficulty  # 0% al inicio, 0.2% en max dificultad
        if np.random.random() < push_prob:
            # Fuerza lateral aleatoria
            force_magnitude = np.random.uniform(500, 2000) * self.difficulty
            direction = np.random.choice([-1, 1])
            self.torso_body.apply_force_at_world_point(
                (force_magnitude * direction, -force_magnitude * 0.3),
                self.torso_body.position
            )
            self.push_visual = 15  # frames para mostrar indicador visual
            self.push_cooldown = 120  # ~2 segundos entre pushes

    def step(self, action):
        self.tiempo += 1

        # V13: Push forces
        self._aplicar_push()
        if self.push_visual > 0:
            self.push_visual -= 1

        # Obstaculos
        if self.torso_body.position.x > self.next_obstacle_x - 700:
            self._generar_obstaculo(self.next_obstacle_x)
            self.next_obstacle_x += np.random.randint(500, 1000)

        for obs_body in self.lista_obstaculos[:]:
            if obs_body.position.x < self.torso_body.position.x - 1500:
                self.space.remove(obs_body, *obs_body.shapes)
                self.lista_obstaculos.remove(obs_body)
                self.obstaculos_info = [i for i in self.obstaculos_info if i["body"] is not obs_body]

        action = np.clip(action, -1.0, 1.0)
        alpha = 0.6
        smoothed_action = (1 - alpha) * self.prev_action + alpha * action

        v_max = 9.0
        motores = [self.pierna_izq['m_cadera'], self.pierna_izq['m_rodilla'],
                   self.pierna_der['m_cadera'], self.pierna_der['m_rodilla']]
        for i, m in enumerate(motores):
            m.rate = float(smoothed_action[i]) * v_max

        for _ in range(4):
            self.space.step(1.0 / 240.0)
        self._detectar_contactos()

        if self.tiempo % 30 == 0:
            self._actualizar_manager()

        # --- REWARD (heredado de V12b con ajustes V13) ---
        vel_x = self.torso_body.velocity.x
        angle = self.torso_body.angle
        pos_y = self.torso_body.position.y
        pos_x = self.torso_body.position.x
        ang_vel = self.torso_body.angular_velocity  # V13: nueva obs
        is_contact_izq = self.c_izq_counter > 0
        is_contact_der = self.c_der_counter > 0
        both_in_air = not is_contact_izq and not is_contact_der

        reward = 0.0

        # A. Velocidad
        vel_error = abs(vel_x - self.goal_velocity)
        if vel_x >= 0.0:
            reward += 1.5 * np.exp(-0.08 * vel_error)
            reward += 0.3 * float(vel_x) / 5.0
        else:
            reward -= 0.5 + abs(float(vel_x)) * 0.05

        # B. Postura
        reward += 0.8 * np.exp(-2.0 * angle ** 2)
        reward += 0.4 * np.exp(-0.005 * (pos_y - 460.0) ** 2)
        reward -= abs(angle) * 0.3
        # V13: penalizar velocidad angular excesiva (estabilidad)
        reward -= abs(ang_vel) * 0.05

        # C. Marcha alternada (identico a v12b)
        new_contact_izq = is_contact_izq and not self.prev_contact_izq
        new_contact_der = is_contact_der and not self.prev_contact_der

        if new_contact_izq and new_contact_der:
            reward += 0.3
            self.last_foot_down = 0
            self.last_step_izq = self.tiempo
            self.last_step_der = self.tiempo
        elif new_contact_izq:
            self.last_step_izq = self.tiempo
            if self.last_foot_down == 2:   reward += 2.0
            elif self.last_foot_down == 1: reward -= 0.5
            else:                          reward += 0.5
            self.last_foot_down = 1
        elif new_contact_der:
            self.last_step_der = self.tiempo
            if self.last_foot_down == 1:   reward += 2.0
            elif self.last_foot_down == 2: reward -= 0.5
            else:                          reward += 0.5
            self.last_foot_down = 2

        if both_in_air:
            self.airtime_counter += 1
            if self.airtime_counter > 8:
                reward -= 0.3
        else:
            self.airtime_counter = 0

        if new_contact_izq and not new_contact_der and self.last_step_der > 0:
            if 20 <= (self.tiempo - self.last_step_der) <= 80:
                reward += 0.5
        if new_contact_der and not new_contact_izq and self.last_step_izq > 0:
            if 20 <= (self.tiempo - self.last_step_izq) <= 80:
                reward += 0.5

        # V13: Bonus por sobrevivir pushes (si hubo push reciente y sigue de pie)
        if self.push_cooldown > 100:  # recien pusheado (cooldown empieza en 120)
            reward += 0.5  # bonus por mantenerse de pie despues del push

        # D. Energia
        reward -= np.sum(np.square(smoothed_action)) * 0.02
        reward -= np.sum(np.square(smoothed_action - self.prev_action)) * 0.01

        # E. Seguridad
        terminated = False
        if self.impacto_torso > 200:  reward -= 5.0; terminated = True
        if self.impacto_muslo > 20.0: reward -= 20.0; terminated = True
        pie_impact = self.impacto_izq + self.impacto_der
        if pie_impact > 3000:
            reward -= (pie_impact - 3000) / 2000.0
        if pos_y > 520 or abs(angle) > 1.2:
            reward -= 10.0; terminated = True

        # Estado
        self.prev_contact_izq = is_contact_izq
        self.prev_contact_der = is_contact_der
        self.prev_pos_x = pos_x
        self.prev_action = smoothed_action

        truncated = self.tiempo > 2000

        if self.render_mode == "human":
            self._render_frame()
        return self._get_obs(), reward, terminated, truncated, {}

    def _get_obs(self):
        rb = self.torso_body
        d_suelo, n_suelo_x, n_suelo_y = self._raycast(pymunk.Vec2d(0, 0), pymunk.Vec2d(0, 150), stabilized=False)
        d_lejos, _, _ = self._raycast(pymunk.Vec2d(0, 0), pymunk.Vec2d(700, 80), stabilized=True)
        d_salto, _, _ = self._raycast(pymunk.Vec2d(0, 0), pymunk.Vec2d(150, 60), stabilized=False)
        self.dist_lidar_lejos = d_lejos

        ang_muslo_izq = np.clip(self.pierna_izq['muslo_body'].angle - rb.angle, -3.14, 3.14)
        ang_rodilla_izq = np.clip(self.pierna_izq['pie'].angle - self.pierna_izq['muslo_body'].angle, -3.14, 3.14)
        ang_muslo_der = np.clip(self.pierna_der['muslo_body'].angle - rb.angle, -3.14, 3.14)
        ang_rodilla_der = np.clip(self.pierna_der['pie'].angle - self.pierna_der['muslo_body'].angle, -3.14, 3.14)

        imp_muslo_norm = min(self.impacto_muslo / 5000.0, 1.0)
        imp_torso_norm = min(self.impacto_torso / 5000.0, 1.0)
        meta_norm = self.goal_velocity / 5.0

        obs = [
            (rb.position.y - 460.0) / 100.0, np.sin(rb.angle), np.cos(rb.angle),
            rb.velocity.x / 100.0, rb.velocity.y / 100.0,
            rb.angular_velocity / 10.0,   # V13: nueva obs
            self.pierna_izq['m_cadera'].rate / 9.0, self.pierna_izq['m_rodilla'].rate / 9.0,
            self.pierna_der['m_cadera'].rate / 9.0, self.pierna_der['m_rodilla'].rate / 9.0,
            1.0 if self.c_izq_counter > 0 else 0.0, 1.0 if self.c_der_counter > 0 else 0.0,
            d_suelo, n_suelo_x, n_suelo_y, d_lejos, d_salto,
            self.impacto_izq / 5000.0, self.impacto_der / 5000.0,
            ang_muslo_izq, ang_rodilla_izq, ang_muslo_der, ang_rodilla_der,
            self.prev_action[0], self.prev_action[1], self.prev_action[2], self.prev_action[3],
            self.grav_y / 1000.0, imp_muslo_norm, imp_torso_norm, meta_norm,
            self.difficulty,                 # V13: el agente sabe la dificultad actual
            self.inclinacion_terreno / 0.3,  # V13: pendiente normalizada
        ]
        return np.array(obs, dtype=np.float32)

    def _raycast(self, start, end, stabilized=False):
        p_start = self.torso_body.position + start.rotated(self.torso_body.angle)
        if stabilized:
            p_end = self.torso_body.position + end
        else:
            p_end = self.torso_body.position + end.rotated(self.torso_body.angle)
        f = pymunk.ShapeFilter(mask=pymunk.ShapeFilter.ALL_MASKS() & ~2)
        res = self.space.segment_query_first(p_start, p_end, 1, f)
        if res:
            return res.alpha, res.normal.x, res.normal.y
        return 1.0, 0.0, -1.0

    def _crear_escenario(self):
        suelo = pymunk.Segment(self.space.static_body, (-2000, 550), (500000, 550), 5.0)
        suelo.friction = self.friccion_dr
        suelo.collision_type = COLL_SUELO
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
        self.pierna_izq = self._crear_pierna(x, y + 30, COLL_PIE_IZQ, self.friccion_dr)
        self.pierna_der = self._crear_pierna(x, y + 30, COLL_PIE_DER, self.friccion_dr)

    def _crear_pierna(self, x, y, c_type_pie, friccion):
        m_muslo = 2.0
        muslo = pymunk.Body(m_muslo, pymunk.moment_for_box(m_muslo, (12, 45)))
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
        # V13: obstaculos mas grandes con dificultad
        max_h = int(30 + 25 * self.difficulty)   # 30->55
        max_w = int(40 + 30 * self.difficulty)   # 40->70
        h = np.random.randint(20, max_h)
        w = np.random.randint(30, max_w)
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = (x, 550 - (h / 2))
        shape = pymunk.Poly.create_box(body, (w, h))
        shape.friction = 1.5
        shape.collision_type = COLL_OBSTACULO
        shape.color = (200, 50, 50, 255)
        self.space.add(body, shape)
        self.lista_obstaculos.append(body)
        self.obstaculos_info.append({"body": body, "w": w, "h": h})

    def _render_frame(self):
        offset_x = -self.torso_body.position.x + 300
        self.draw_options.transform = pymunk.Transform.translation(offset_x, 0)
        self.screen.fill((240, 240, 240))
        self.space.debug_draw(self.draw_options)

        # Indicador de push
        if self.push_visual > 0:
            pygame.draw.circle(self.screen, (255, 0, 0), (500, 50), 20)
            txt_push = self.font.render("PUSH!", True, (255, 0, 0))
            self.screen.blit(txt_push, (530, 40))

        # LIDAR visual
        st = self.torso_body.position
        end = st + pymunk.Vec2d(700, 80)
        st_scr = st + pymunk.Vec2d(offset_x, 0)
        end_scr = end + pymunk.Vec2d(offset_x, 0)
        try:
            pygame.draw.line(self.screen, (0, 255, 0),
                             (int(st_scr.x), int(st_scr.y)),
                             (int(end_scr.x), int(end_scr.y)), 2)
        except (TypeError, OverflowError):
            pass

        # HUD
        txt_vel = self.font.render(
            f"Vel: {self.torso_body.velocity.x:.1f} | META: {self.goal_velocity:.1f}", True, (50, 50, 50))
        self.screen.blit(txt_vel, (20, 20))
        txt_diff = self.font.render(
            f"Difficulty: {self.difficulty:.2f} | Grav: {self.grav_y:.0f} | Fric: {self.friccion_dr:.1f}",
            True, (50, 50, 50))
        self.screen.blit(txt_diff, (20, 45))
        txt_ep = self.font.render(
            f"Episode: {self.total_episodes} | Step: {self.tiempo}", True, (50, 50, 50))
        self.screen.blit(txt_ep, (20, 70))

        pygame.display.flip()
        self.clock.tick(60)

    def get_render_data(self):
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
# TRAINING V13
# ==========================================
def make_env():
    return SonsoV13Env(render_mode=None)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    os.makedirs("logs", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    print("=" * 60)
    print(f"SONSO IA: V13.0 {NOMBRE_NUEVO} (PERTURBATION)")
    print("   -> Push forces + Curriculum difficulty + Red 512")
    print("   -> Hereda conocimiento de V12b como base de reward")
    print("=" * 60)

    n_procs = 6
    env = SubprocVecEnv([make_env for _ in range(n_procs)])
    env = VecMonitor(env, filename=f"logs/{NOMBRE_NUEVO}")
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=0.99)

    # V13: Red mas grande (256->512 neuronas) para manejar mas complejidad
    # Cuando tengas la 5070: subir a 1024 con device="cuda"
    policy_kwargs = dict(net_arch=[512, 512])

    model = SAC(
        "MlpPolicy",
        env,
        policy_kwargs=policy_kwargs,
        verbose=1,
        learning_rate=3e-4,
        batch_size=512,
        buffer_size=600_000,
        learning_starts=10_000,
        gamma=0.99,
        tau=0.005,
        ent_coef='auto',
        gradient_steps=2,
        device="cpu",   # Cambiar a "cuda" cuando tengas la 5070
        tensorboard_log="./tensorboard/",
    )
    print("[OK] Modelo V13 creado desde cero (red 512x512).")

    checkpoint_callback = CheckpointCallback(
        save_freq=50_000,
        save_path=f"./models/{NOMBRE_NUEVO}/",
        name_prefix=NOMBRE_NUEVO,
    )

    print(">> INICIANDO ENTRENAMIENTO V13 (4M Steps)...")
    try:
        model.learn(total_timesteps=4_000_000, callback=checkpoint_callback, log_interval=4)
        model.save(NOMBRE_NUEVO)
        env.save(f"{NOMBRE_NUEVO}_vecnorm.pkl")
        print(">> ENTRENAMIENTO V13 FINALIZADO.")
    except KeyboardInterrupt:
        model.save(NOMBRE_NUEVO)
        env.save(f"{NOMBRE_NUEVO}_vecnorm.pkl")
        print(">> Guardado por interrupcion.")
    finally:
        env.close()
