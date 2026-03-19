"""
enjoy_export.py — Corre el modelo de Sonso y guarda la trayectoria en JSON para Blender.

Uso:
    python enjoy_export.py

Genera: sonso_trajectory.json  (importar desde blender_sonso.py)
"""
import json
from stable_baselines3 import SAC
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from main_ppo import SonsoEnv

MODELO  = "sonso_v12_gait"
VECNORM = "sonso_v12_gait_vecnorm.pkl"
OUTPUT  = "sonso_trajectory.json"
MAX_FRAMES = 1200   # ~20 segundos a 60 fps

env_fn  = lambda: SonsoEnv(render_mode="human")
raw_env = DummyVecEnv([env_fn])
env     = VecNormalize.load(VECNORM, raw_env)
env.training = False
env.norm_reward = False
model   = SAC.load(MODELO, env=env)

obs = env.reset()
trajectory = []
print(f">> Grabando hasta {MAX_FRAMES} frames... Ctrl+C para parar antes.")

try:
    for frame in range(MAX_FRAMES):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, info = env.step(action)
        inner = env.envs[0]           # env interno sin normalización
        trajectory.append(inner.get_render_data())
        if done[0]:
            obs = env.reset()
except KeyboardInterrupt:
    print("\n>> Grabación interrumpida.")
finally:
    env.close()

with open(OUTPUT, "w") as f:
    json.dump(trajectory, f)
print(f">> Guardado: {OUTPUT}  ({len(trajectory)} frames)")
print(f">> Ahora abre Blender y corre blender_sonso.py")
