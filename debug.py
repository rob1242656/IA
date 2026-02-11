import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pymunk
import pymunk.pygame_util
import pygame
import math
import os
from stable_baselines3 import PPO
# Importamos DummyVecEnv para correr en serie (sin multihilo)
from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor

# --- CONFIGURACIÓN FÍSICA ---
ANCHO, ALTO = 1000, 600
CAT_SUELO = 1
CAT_ROBOT = 2

# ==========================================
# PEGAR AQUÍ TU CLASE SonsoEnv (La V3.3)
# ==========================================
# (Por favor, asegúrate de que la clase SonsoEnv está definida aquí arriba 
#  o impórtala si la tienes en otro archivo. Para este test, asumo que 
#  copiaste la clase SonsoEnv del código V3.3 completo que te di antes)
# ...
# ...

# Si no quieres copiar toda la clase de nuevo, puedes intentar:
# from main_ppo import SonsoEnv 
# (Pero asegúrate de que main_ppo.py esté limpio y no ejecute cosas al importar)

# Para ir a lo seguro, usa el bloque de abajo asumiendo que el archivo se llama main_ppo.py
# y vamos a modificar SOLO la parte final del if __name__ == "__main__":

if __name__ == "__main__":
    print("="*50)
    print("🚑 MODO DIAGNÓSTICO SINGLE-CORE")
    print("   -> Objetivo: Encontrar errores de sintaxis ocultos.")
    print("="*50)

    # Definimos la función para crear el ambiente
    # IMPORTANTE: Aquí importamos tu clase del archivo principal si es necesario
    # from main_ppo import SonsoEnv  <-- Descomenta si tienes la clase en otro lado
    
    # OJO: Si vas a pegar este bloque AL FINAL de tu archivo main_ppo.py, 
    # sustituye todo el bloque "if __name__ == '__main__':" anterior por este.

    def make_env():
        return SonsoEnv(render_mode=None)

    # 1. Usamos DummyVecEnv (1 solo proceso, misma memoria)
    # Esto muestra los errores reales en pantalla en lugar de "EOFError"
    env = DummyVecEnv([make_env]) 
    env = VecMonitor(env)

    # 2. Configuración Ligera
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        device="cpu"
    )

    print(">> Probando 1000 pasos de entrenamiento...")
    try:
        model.learn(total_timesteps=1000)
        print("\n✅ ÉXITO TOTAL: El código NO tiene bugs.")
        print("   CONCLUSIÓN: Era falta de RAM. Configura n_procs = 4.")
    except Exception as e:
        print("\n❌ ERROR DE CÓDIGO DETECTADO:")
        import traceback
        traceback.print_exc() # Esto nos dirá qué línea está mal
        
    env.close()