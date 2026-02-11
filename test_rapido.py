import pymunk
print(f"Versión Pymunk: {pymunk.version}")
space = pymunk.Space()
if hasattr(space, 'add_collision_handler'):
    print("✅ ÉXITO: add_collision_handler EXISTE. ¡Lanzar Juego!")
else:
    print("❌ FRACASO: Sigue faltando. Hay un fantasma en tu máquina.")