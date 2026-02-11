import gymnasium as gym
import pygame
import os
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

# --- CONFIGURACIÓN ---
# Nombre exacto del modelo V7.1 que acabas de entrenar
NOMBRE_MODELO = "sonso_v71_ryzen_turbo"

try:
    # Importamos la clase del entorno desde tu archivo de entrenamiento
    # Si tu archivo tiene otro nombre, cambia 'main_ppo' por ese nombre
    from main_ppo import SonsoEnv 
except ImportError:
    print("❌ ERROR CRÍTICO: No encuentro el archivo 'main_ppo.py'.")
    print("   -> Solución: Renombra tu script de entrenamiento V7.1 a 'main_ppo.py'")
    exit()

def visualizar():
    print("="*60)
    print(f"👁️ VISUALIZADOR BIOMECÁNICO V7.1")
    print(f"   -> Modelo: {NOMBRE_MODELO}")
    print("="*60)

    # 1. Verificar archivos
    if not os.path.exists(f"{NOMBRE_MODELO}.zip"):
        print(f"❌ No encuentro el modelo {NOMBRE_MODELO}.zip")
        return
    if not os.path.exists(f"{NOMBRE_MODELO}_vecnorm.pkl"):
        print(f"⚠️ ADVERTENCIA: No encuentro {NOMBRE_MODELO}_vecnorm.pkl")
        print("   -> El robot se moverá como si estuviera borracho (sin normalización).")

    # 2. Crear entorno Dummy (Una sola instancia para renderizar)
    # render_mode='human' activa la ventana de Pygame
    env = DummyVecEnv([lambda: SonsoEnv(render_mode="human")])

    # 3. Cargar Gafas (Normalización)
    # Esto es vital: ajusta lo que el robot "ve" a lo que aprendió
    try:
        env = VecNormalize.load(f"{NOMBRE_MODELO}_vecnorm.pkl", env)
        env.training = False     # No actualizar estadísticas (solo lectura)
        env.norm_reward = False  # No normalizar recompensa (queremos ver la real)
        print("✅ Stats de normalización cargadas (Visión calibrada).")
    except Exception as e:
        print(f"⚠️ Error cargando normalización: {e}")

    # 4. Cargar Cerebro (Modelo PPO)
    print("⏳ Cargando red neuronal...")
    model = PPO.load(NOMBRE_MODELO)
    print("✅ Modelo cargado. ¡Iniciando simulación!")

    # 5. Bucle de Simulación
    obs = env.reset()
    
    try:
        while True:
            # deterministic=True obliga al robot a usar su mejor jugada aprendida
            # (sin ruido aleatorio de exploración)
            action, _ = model.predict(obs, deterministic=True)
            
            obs, reward, done, info = env.step(action)
            
            # Gestión de cierre de ventana
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    env.close()
                    exit()
            
            # Si el episodio termina (caída o timeout), reiniciamos
            if done[0]:
                obs = env.reset()
                print(">> Reiniciando episodio...")

    except KeyboardInterrupt:
        print("\n👋 Visualización finalizada.")
        env.close()

if __name__ == "__main__":
    visualizar()