import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pymunk
import pymunk.pygame_util
import pygame
import math
import os
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

# --- CONFIGURACIÓN FÍSICA ---
ANCHO, ALTO = 1000, 600
CAT_SUELO = 1
CAT_ROBOT = 2

# ==========================================
# 1. ENTORNO GYMNASIUM (V3.3 STEALTH)
# ==========================================
class SonsoEnv(gym.Env):
    metadata = {'render_modes': ['human'], 'render_fps': 60}

    def __init__(self, render_mode=None):
        super(SonsoEnv, self).__init__()
        self.render_mode = render_mode
        
        # Acción Continua (4 Motores)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
        
        # --- CAMBIO 1: OBSERVACIÓN AMPLIADA (18 Sensores) ---
        # Añadimos 2 sensores de fuerza de impacto (Load Cells)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(18,), dtype=np.float32)
        
        # Filtro y Memoria
        self.prev_action = np.zeros(4)
        self.ultimo_pie_contacto = 0
        
        # Variables de Sensores de Fuerza
        self.impacto_izq = 0.0
        self.impacto_der = 0.0

        if self.render_mode == 'human':
            pygame.init()
            self.screen = pygame.display.set_mode((ANCHO, ALTO))
            pygame.display.set_caption("Sonso IA: V3.3 STEALTH WALKER")
            self.clock = pygame.time.Clock()
            self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.space = pymunk.Space()
        self.space.gravity = (0.0, 900.0)
        
        # --- CAMBIO 2: HANDLERS CON SENSOR DE FUERZA (Post-Solve) ---
        h_izq = self.space.add_collision_handler(2, CAT_SUELO)
        h_izq.begin = self._pie_toca
        h_izq.separate = self._pie_suelta
        h_izq.post_solve = self._leer_fuerza_izq # Nuevo sensor

        h_der = self.space.add_collision_handler(3, CAT_SUELO)
        h_der.begin = self._pie_toca
        h_der.separate = self._pie_suelta
        h_der.post_solve = self._leer_fuerza_der # Nuevo sensor
        
        self.contacto_izq = 0; self.contacto_der = 0
        self.impacto_izq = 0.0; self.impacto_der = 0.0
        self.last_x = 200
        self.tiempo = 0
        self.prev_action = np.zeros(4)
        self.ultimo_pie_contacto = 0
        
        self._crear_escenario()
        self._crear_robot(200, 420) 
        
        return self._get_obs(), {}

    # --- LECTURA DE SENSORES DE FUERZA ---
    def _leer_fuerza_izq(self, arbiter, space, data):
        # El impulso es un vector, tomamos su magnitud
        self.impacto_izq = arbiter.total_impulse.length
        return True

    def _leer_fuerza_der(self, arbiter, space, data):
        self.impacto_der = arbiter.total_impulse.length
        return True

    def step(self, action):
        self.tiempo += 1
        
        # Reset de sensores de impacto (son instantáneos por frame)
        self.impacto_izq = 0.0
        self.impacto_der = 0.0
        
        # Filtro Pasa-Bajos
        alpha = 0.3
        smoothed_action = (1 - alpha) * self.prev_action + alpha * action
        self.prev_action = smoothed_action
        
        v_max = 6.0
        motores = [
            self.pierna_izq['m_cadera'], self.pierna_izq['m_rodilla'],
            self.pierna_der['m_cadera'], self.pierna_der['m_rodilla']
        ]
        for i, motor in enumerate(motores):
            motor.rate = float(smoothed_action[i]) * v_max

        # Simulación
        for _ in range(4): self.space.step(1.0 / 240.0)
        
        # Telemetría
        pos_x = self.torso_body.position.x
        angle = self.torso_body.angle
        
        reward = 0
        
        # A) Avance (x15 según tu última orden)
        avance = pos_x - self.last_x
        reward += avance * 15.0
        self.last_x = pos_x
        
        # B) Simetría
        if self.contacto_izq and self.ultimo_pie_contacto != 1:
            reward += 2.0; self.ultimo_pie_contacto = 1
        elif self.contacto_der and self.ultimo_pie_contacto != 2:
            reward += 2.0; self.ultimo_pie_contacto = 2
            
        # C) Eficiencia Energética
        reward -= np.sum(np.square(smoothed_action)) * 0.05
        
        # D) Estabilidad
        reward -= abs(angle) * 3.0
        
        # --- CAMBIO 3: PENALIZACIÓN POR IMPACTO BRUSCO (Stealth) ---
        # Si la fuerza total de impacto supera 2000 unidades, castigamos.
        # Esto enseña al robot a "amortiguar" la caída.
        fuerza_total = self.impacto_izq + self.impacto_der
        if fuerza_total > 2000:
            reward -= (fuerza_total / 5000.0) # Castigo proporcional al estruendo
            
        # E) Bono Vida
        reward += 0.1

        terminated = False
        truncated = False
        if self.torso_body.position.y > 500 or abs(angle) > 1.8:
            reward -= 10
            terminated = True
        if self.tiempo > 1000: truncated = True

        if self.render_mode == "human": self._render_frame()

        return self._get_obs(), reward, terminated, truncated, {}

    def _get_obs(self):
        rb = self.torso_body
        d_suelo, n_suelo = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(0, 100))
        d_pared, _ = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(150, 0))
        d_arriba, _ = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(0, -100))
        d_atras, _ = self._raycast(pymunk.Vec2d(0,0), pymunk.Vec2d(-100, 0))
        
        # Normalizamos el impacto (aprox 0-1) para la red neuronal
        imp_izq = min(self.impacto_izq / 5000.0, 1.0)
        imp_der = min(self.impacto_der / 5000.0, 1.0)

        obs = [
            (rb.position.y - 400) / 200.0,
            rb.angle / 3.14,
            rb.velocity.x / 100.0,
            rb.velocity.y / 100.0,
            self.pierna_izq['m_cadera'].rate / 6.0,
            self.pierna_izq['m_rodilla'].rate / 6.0,
            self.pierna_der['m_cadera'].rate / 6.0,
            self.pierna_der['m_rodilla'].rate / 6.0,
            float(self.contacto_izq),
            float(self.contacto_der),
            d_suelo,
            rb.velocity.y / 100.0, 
            n_suelo,
            1.0 if d_pared < 0.05 else 0.0,
            d_arriba,
            d_atras,
            # --- NUEVOS INPUTS (17 y 18) ---
            imp_izq,
            imp_der
        ]
        return np.array(obs, dtype=np.float32)

    def _raycast(self, start, end):
        p_start = self.torso_body.position + start.rotated(self.torso_body.angle)
        p_end = self.torso_body.position + end.rotated(self.torso_body.angle)
        f = pymunk.ShapeFilter(mask=0xFFFFFFFF ^ CAT_ROBOT)
        res = self.space.segment_query_first(p_start, p_end, 1, f)
        if res: return res.alpha, res.normal.x
        return 1.0, 0.0

    def _crear_escenario(self):
        suelo = pymunk.Segment(self.space.static_body, (-1000, 550), (20000, 550), 5.0)
        suelo.friction = 1.0; suelo.collision_type = CAT_SUELO
        self.space.add(suelo)

    def _crear_robot(self, x, y):
        # Hardware V2.4 Specs
        masa_torso = 8.0 
        self.torso_body = pymunk.Body(masa_torso, pymunk.moment_for_box(masa_torso, (40, 60)))
        self.torso_body.position = (x, y)
        shape = pymunk.Poly.create_box(self.torso_body, (40, 60))
        shape.filter = pymunk.ShapeFilter(group=CAT_ROBOT, categories=CAT_ROBOT)
        shape.friction = 0.5
        self.space.add(self.torso_body, shape)
        
        self.pierna_izq = self._crear_pierna(x, y+30, 2)
        self.pierna_der = self._crear_pierna(x, y+30, 3)

    def _crear_pierna(self, x, y, c_type):
        m_muslo = 2.0
        muslo = pymunk.Body(m_muslo, pymunk.moment_for_box(m_muslo, (12, 45)))
        muslo.position = (x, y + 25)
        m_shape = pymunk.Poly.create_box(muslo, (12, 45))
        m_shape.filter = pymunk.ShapeFilter(group=CAT_ROBOT, categories=CAT_ROBOT)
        
        pivot = pymunk.PivotJoint(self.torso_body, muslo, (0, 25), (0, -20))
        motor = pymunk.SimpleMotor(self.torso_body, muslo, 0)
        motor.max_force = 450000 
        limite = pymunk.RotaryLimitJoint(self.torso_body, muslo, -1.2, 0.4)
        self.space.add(muslo, m_shape, pivot, motor, limite)
        
        panto = pymunk.Body(1.0, pymunk.moment_for_box(1.0, (10, 45)))
        panto.position = (x, y + 65)
        p_shape = pymunk.Poly.create_box(panto, (10, 45))
        p_shape.filter = pymunk.ShapeFilter(group=CAT_ROBOT, categories=CAT_ROBOT)
        p_shape.friction = 3.5 
        p_shape.collision_type = c_type
        
        pivot_r = pymunk.PivotJoint(muslo, panto, (0, 20), (0, -20))
        motor_r = pymunk.SimpleMotor(muslo, panto, 0)
        motor_r.max_force = 350000 
        limite_r = pymunk.RotaryLimitJoint(muslo, panto, 0.0, 2.2) 
        self.space.add(panto, p_shape, pivot_r, motor_r, limite_r)
        
        return {'m_cadera': motor, 'm_rodilla': motor_r}

    def _render_frame(self):
        self.screen.fill((240, 240, 240))
        self.space.debug_draw(self.draw_options)
        pygame.display.flip()
        self.clock.tick(60)

# ==========================================
# 2. BLOQUE DE ENTRENAMIENTO (Batch 256)
# ==========================================
def make_env():
    return SonsoEnv(render_mode=None)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    print("="*50)
    print("🚀 SONSO IA: STEALTH MODE V3.3 ACTIVADO")
    print("   -> Sensores: 18 (Incluye Presión)")
    print("   -> Batch Size: 256 (Ryzen Optimized)")
    print("="*50)

    n_procs = 8 
    env = SubprocVecEnv([make_env for _ in range(n_procs)])
    env = VecMonitor(env)

    model_path = "sonso_stealth_v33"
    
    # --- CAMBIO 4: BATCH SIZE OPTIMIZADO (256) ---
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=2.5e-4,   
        n_steps=4096,           
        batch_size=256,         # ¡Aquí está tu turbo para el Ryzen!
        n_epochs=10,            
        gamma=0.99,
        gae_lambda=0.95,
        ent_coef=0.01,          
        verbose=1,
        device="cpu"
    )

    print(">> Iniciando entrenamiento masivo...")
    try:
        model.learn(total_timesteps=1_000_000)
        model.save(model_path)
    except KeyboardInterrupt:
        model.save(model_path)

    env.close()

    print("\n>> Visualización STEALTH...")
    env_vis = SonsoEnv(render_mode="human")
    model = PPO.load(model_path)
    
    obs, _ = env_vis.reset()
    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env_vis.step(action)
        if terminated or truncated:
            obs, _ = env_vis.reset()