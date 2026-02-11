import sys
import os

print("="*40)
print("   SONDA DE DIAGNÓSTICO - IA ARCHITECT")
print("="*40)

# 1. ¿Dónde estamos?
print(f"Directorio de Trabajo: {os.getcwd()}")

# 2. ¿Qué archivos hay aquí que puedan causar conflicto?
print("\n[ARCHIVOS LOCALES EN CONFLICTO POTENCIAL]")
archivos_locales = os.listdir()
conflicto = False
for f in archivos_locales:
    if "pymunk" in f.lower():
        print(f" -> ¡ALERTA! Encontrado: {f}")
        conflicto = True
if not conflicto:
    print(" -> Ningún archivo 'pymunk' visible localmente (Bien).")

# 3. Importación y origen
print("\n[INTENTO DE IMPORTACIÓN]")
try:
    import pymunk
    print(f" -> ÉXITO: Pymunk importado.")
    print(f" -> UBICACIÓN REAL: {pymunk.__file__}")
    print(f" -> VERSIÓN REPORTADA: {getattr(pymunk, 'version', 'Desconocida')}")
    
    # 4. Inspección del Objeto Space
    print("\n[INSPECCIÓN DE CLASE SPACE]")
    if hasattr(pymunk, 'Space'):
        space = pymunk.Space()
        print(f" -> Space creado: {space}")
        
        # EL TEST DEFINITIVO
        if hasattr(space, 'add_collision_handler'):
            print(" -> ESTADO: OPERATIVO (add_collision_handler existe).")
        else:
            print(" -> ESTADO: CRÍTICO (add_collision_handler NO existe).")
            print("    Esto sugiere una versión muy antigua (v4/v5) o corrupta.")
            print("    Atributos disponibles en Space:", dir(space))
    else:
        print(" -> ERROR FATAL: pymunk no tiene la clase 'Space'.")

except ImportError as e:
    print(f" -> ERROR DE IMPORTACIÓN: {e}")
except Exception as e:
    print(f" -> ERROR GENERAL: {e}")

print("="*40)