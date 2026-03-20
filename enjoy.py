"""
enjoy.py — Ver al Sonso caminar en tiempo real + exportar trayectoria para Blender
================================================================================
Uso:
  python enjoy.py                  -> Solo visualizar (modelo final)
  python enjoy.py --export         -> Visualizar + guardar trayectoria JSON
  python enjoy.py --checkpoint X   -> Usar checkpoint especifico (ej: 3300000)
"""
import argparse
import json
import numpy as np
from stable_baselines3 import SAC
from stable_baselines3.common.vec_env import VecNormalize, DummyVecEnv
from main_ppo import SonsoEnv

MODELO = "sonso_v12b_gait_fixed"
VECNORM = "sonso_v12b_gait_fixed_vecnorm.pkl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true", help="Exportar trayectoria JSON para Blender")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Usar checkpoint especifico (ej: 3300000)")
    parser.add_argument("--episodes", type=int, default=5, help="Episodios a correr")
    args = parser.parse_args()

    if args.checkpoint:
        modelo_path = f"models/sonso_v12b_gait_fixed/sonso_v12b_gait_fixed_{args.checkpoint}_steps"
    else:
        modelo_path = MODELO

    # Env para visualizacion (SIN VecNormalize - usamos obs raw)
    env = SonsoEnv(render_mode="human")

    # Cargar VecNormalize stats para normalizar obs manualmente
    dummy = DummyVecEnv([lambda: SonsoEnv(render_mode=None)])
    vec_norm = VecNormalize.load(VECNORM, dummy)
    vec_norm.training = False
    vec_norm.norm_reward = False

    model = SAC.load(modelo_path, device="cpu")

    print(f">> Modelo cargado: {modelo_path}")
    print(f">> Episodios: {args.episodes} | Export: {args.export}")
    print(">> Ctrl+C para salir\n")

    trayectoria = []
    total_reward = 0.0

    for ep in range(args.episodes):
        obs_raw, _ = env.reset()
        ep_reward = 0.0
        ep_steps = 0
        done = False

        while not done:
            # Normalizar obs manualmente usando las stats del VecNormalize
            obs_norm = vec_norm.normalize_obs(obs_raw)

            action, _ = model.predict(obs_norm, deterministic=True)
            obs_raw, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            ep_steps += 1
            done = terminated or truncated

            if args.export:
                trayectoria.append(env.get_render_data())

        total_reward += ep_reward
        print(f"  Episodio {ep+1}/{args.episodes} | Steps: {ep_steps} ({ep_steps/60:.1f}s) | Reward: {ep_reward:.0f}")

    print(f"\n>> Promedio: {total_reward/args.episodes:.0f} reward")

    if args.export and trayectoria:
        out_path = "sonso_trajectory.json"
        with open(out_path, "w") as f:
            json.dump(trayectoria, f)
        print(f">> Trayectoria exportada: {out_path} ({len(trayectoria)} frames)")
        print(">> Ahora abre Blender y corre blender_sonso.py")

    dummy.close()
    print(">> Listo.")


if __name__ == "__main__":
    main()
