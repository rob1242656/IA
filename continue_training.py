import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor, VecNormalize
from stable_baselines3.common.callbacks import CheckpointCallback

# Importamos la clase del entorno V5.1
from main_ppo import SonsoEnv, make_env

# El nombre del modelo V5.1
NOMBRE_MODELO = "sonso_v51_eagle_eye"

if __name__ == "__main__":
    print(f"RETOMANDO ENTRENAMIENTO: {NOMBRE_MODELO}")
    
    n_procs = 8
    env = SubprocVecEnv([make_env for _ in range(n_procs)])
    env = VecMonitor(env, filename=f"logs/{NOMBRE_MODELO}")
    
    # 1. Cargar entorno previo (Normalización)
    print(">> Cargando entorno...")
    try:
        env = VecNormalize.load(f"{NOMBRE_MODELO}_vecnorm.pkl", env)
        env.training = True 
        env.norm_reward = True
    except:
        print("ERROR: No encuentro el archivo _vecnorm.pkl. ¿Ejecutaste el entrenamiento inicial?")
        exit()

    # 2. Cargar modelo
    print(">> Cargando modelo...")
    try:
        model = PPO.load(NOMBRE_MODELO, env=env)
    except:
        print(f"ERROR: No encuentro {NOMBRE_MODELO}.zip")
        exit()

    # Callback para seguir guardando
    checkpoint_callback = CheckpointCallback(save_freq=100000, save_path=f'./models/{NOMBRE_MODELO}/', name_prefix=NOMBRE_MODELO)

    # 3. Entrenar 2 millones de pasos extra
    print(">> Entrenando...")
    try:
        model.learn(total_timesteps=2_000_000, callback=checkpoint_callback)
        model.save(NOMBRE_MODELO)
        env.save(f"{NOMBRE_MODELO}_vecnorm.pkl")
        print(">> FIN DEL RE-ENTRENAMIENTO.")
    except KeyboardInterrupt:
        model.save(NOMBRE_MODELO)
        env.save(f"{NOMBRE_MODELO}_vecnorm.pkl")
        print(">> Guardado de emergencia completado.")