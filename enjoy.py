import gymnasium as gym
from stable_baselines3 import SAC
import time

# 1. Cargamos el modelo que dejaste entrenando (asegúrate de que el nombre coincida)
# Puedes usar el checkpoint de 1.5M o el final de 3M
path = "models/sonso_v91_smart_manager/sonso_v91_smart_manager_2200000_steps" 

# 2. Creamos el entorno en modo humano para ver el video
# Nota: Importamos tu clase SonsoEnv desde tu archivo principal
from main_ppo import SonsoEnv 

env = SonsoEnv(render_mode="human")

model = SAC.load(path)

obs, _ = env.reset()
print(">> Iniciando demostración para el portafolio...")

try:
    while True:
        action, _states = model.predict(obs, deterministic=True) # deterministic=True para que no 'baile'
        obs, reward, terminated, truncated, info = env.step(action)
        
        if terminated or truncated:
            obs, _ = env.reset()
            
except KeyboardInterrupt:
    print(">> Grabación finalizada.")
    env.close()