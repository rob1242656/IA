"""
blender_sonso.py — Visualización 3D de Sonso (estilo AI Warehouse)
==================================================================
Cómo usar:
  1. Abre Blender
  2. Ve a la pestaña "Scripting"
  3. Pega este código (o ábrelo con "Open")
  4. Ajusta TRAJ_FILE a la ruta donde generaste sonso_trajectory.json
  5. Click en "Run Script"
  6. Spacebar para ver la animación
  7. Ctrl+F12 para renderizar
"""

import bpy
import json
import math

# ─────────────────────────────────────────────
# CONFIGURACIÓN — ajusta esta ruta si es necesario
# ─────────────────────────────────────────────
TRAJ_FILE = r"C:\Users\wenas\OneDrive\Escritorio\Ia\sonso_trajectory.json"

# Conversión de escala: 1 pixel Pymunk = 0.01 metros Blender
SCALE     = 0.01
GROUND_PY = 550   # y del suelo en Pymunk (para convertir a z=0 en Blender)


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

def px_to_bl(x, y):
    """Convierte posición Pymunk (x hacia derecha, y hacia abajo)
    a Blender (x derecha, y profundidad=0, z arriba). Suelo queda en z=0."""
    return (x * SCALE, 0.0, (GROUND_PY - y) * SCALE)


def make_material(name, color_rgb, metallic=0.8, roughness=0.2, emission=None):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf   = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value  = (*color_rgb, 1.0)
    bsdf.inputs["Metallic"].default_value    = metallic
    bsdf.inputs["Roughness"].default_value   = roughness

    if emission:
        bsdf.inputs["Emission Color"].default_value  = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.4

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def make_box(name, px_w, px_h, depth_m, color, metallic=0.8, roughness=0.2, emission=None):
    """Crea una caja centrada en el origen, con dimensiones en metros."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    # Escalar: cube tiene size=1 (-0.5 a 0.5) → multiplicamos por dimensiones reales
    obj.scale = (px_w * SCALE, depth_m, px_h * SCALE)
    bpy.ops.object.transform_apply(scale=True)

    # Bevel para suavizar esquinas
    bpy.ops.object.modifier_add(type='BEVEL')
    obj.modifiers["Bevel"].width = 0.015
    obj.modifiers["Bevel"].segments = 3
    bpy.ops.object.modifier_apply(modifier="Bevel")

    mat = make_material(name + "_mat", color, metallic, roughness, emission)
    obj.data.materials.append(mat)
    return obj


def insert_transform_keyframe(obj, frame):
    obj.keyframe_insert(data_path="location",       frame=frame)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


# ─────────────────────────────────────────────
# 1. LIMPIAR ESCENA
# ─────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for col in bpy.data.collections:
    bpy.data.collections.remove(col)

# ─────────────────────────────────────────────
# 2. LEER TRAYECTORIA
# ─────────────────────────────────────────────
with open(TRAJ_FILE, "r") as f:
    traj = json.load(f)

n_frames = len(traj)
print(f"[Sonso] Cargados {n_frames} frames de trayectoria.")

# ─────────────────────────────────────────────
# 3. SUELO
# ─────────────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=1)
suelo = bpy.context.active_object
suelo.name = "Suelo"
# El robot se mueve hasta ~500000 px a la derecha → cubrimos ~200 m
suelo.scale = (2500, 10, 1)
bpy.ops.object.transform_apply(scale=True)
suelo.location = (50.0, 0, 0)

mat_suelo = make_material("Suelo_mat", (0.06, 0.06, 0.06), metallic=0.0, roughness=0.95)
# Agregar cuadriculado sutil con textura de coordenadas
suelo.data.materials.append(mat_suelo)

# Líneas de cuadrícula (plano con Wireframe modifier)
bpy.ops.mesh.primitive_plane_add(size=1)
grid = bpy.context.active_object
grid.name = "Grid"
grid.scale = (2500, 10, 1)
bpy.ops.object.transform_apply(scale=True)
grid.location = (50.0, 0, 0.001)
bpy.ops.object.modifier_add(type='WIREFRAME')
grid.modifiers["Wireframe"].thickness = 0.005
mat_grid = make_material("Grid_mat", (0.15, 0.15, 0.15), metallic=0.0, roughness=1.0)
grid.data.materials.append(mat_grid)

# ─────────────────────────────────────────────
# 4. ROBOT — crear partes
# ─────────────────────────────────────────────
# Colores: torso azul, muslos cian, pies turquesa
AZUL    = (0.05, 0.40, 0.90)
CIAN    = (0.10, 0.65, 0.85)
TURQ    = (0.15, 0.75, 0.70)

torso     = make_box("Torso",    40, 60, 0.30, AZUL,  metallic=0.9, roughness=0.15, emission=AZUL)
muslo_izq = make_box("MusloIzq", 12, 45, 0.20, CIAN,  metallic=0.8, roughness=0.20)
muslo_der = make_box("MusloDer", 12, 45, 0.20, CIAN,  metallic=0.8, roughness=0.20)
pie_izq   = make_box("PieIzq",   10, 45, 0.18, TURQ,  metallic=0.7, roughness=0.25)
pie_der   = make_box("PieDer",   10, 45, 0.18, TURQ,  metallic=0.7, roughness=0.25)

partes = {
    "torso":     torso,
    "muslo_izq": muslo_izq,
    "muslo_der": muslo_der,
    "pie_izq":   pie_izq,
    "pie_der":   pie_der,
}

# Separar las piernas en Y para que no se solapen visualmente
muslo_izq.location.y = -0.12
muslo_der.location.y =  0.12
pie_izq.location.y   = -0.10
pie_der.location.y   =  0.10

# ─────────────────────────────────────────────
# 5. OBSTÁCULOS (de la trayectoria)
# ─────────────────────────────────────────────
# Recopilar obstáculos únicos por posición X (evitar duplicados)
obs_vistos = {}
for fr in traj:
    for ob in fr["obstacles"]:
        key = round(ob["x"])
        if key not in obs_vistos:
            obs_vistos[key] = ob

for key, ob in obs_vistos.items():
    ob_obj = make_box(f"Obs_{key}", ob["w"], ob["h"], 0.60,
                      (0.75, 0.15, 0.10), metallic=0.3, roughness=0.7)
    bx, by, bz = px_to_bl(ob["x"], ob["y"])
    ob_obj.location = (bx, by, bz)

# ─────────────────────────────────────────────
# 6. KEYFRAMES — animar el robot
# ─────────────────────────────────────────────
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end   = n_frames

PART_KEYS = ["torso", "muslo_izq", "muslo_der", "pie_izq", "pie_der"]

for fi, frame_data in enumerate(traj):
    f = fi + 1
    bpy.context.scene.frame_set(f)

    for key in PART_KEYS:
        obj = partes[key]
        d   = frame_data[key]

        bx, by, bz = px_to_bl(d["x"], d["y"])

        # Offset Y para las piernas (misma separación que al crearlas)
        if key == "muslo_izq": by = -0.12
        elif key == "muslo_der": by = 0.12
        elif key == "pie_izq":  by = -0.10
        elif key == "pie_der":  by = 0.10

        obj.location         = (bx, by, bz)
        obj.rotation_euler.y = -d["angle"]   # Pymunk→Blender: invertir eje Y
        insert_transform_keyframe(obj, f)

# Suavizar curvas de animación (interpolación Bezier → Linear para física realista)
for obj in partes.values():
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

# ─────────────────────────────────────────────
# 7. CÁMARA (sigue al torso)
# ─────────────────────────────────────────────
bpy.ops.object.camera_add(location=(0, -8, 2.5))
cam = bpy.context.active_object
cam.name = "Camera_Sonso"
cam.rotation_euler = (math.radians(75), 0, 0)
cam.data.lens = 35   # focal length
bpy.context.scene.camera = cam

# Follow constraint hacia el torso (eje X)
follow = cam.constraints.new("COPY_LOCATION")
follow.target = torso
follow.use_x  = True
follow.use_y  = False
follow.use_z  = False
follow.use_offset = True   # mantiene el offset de -8 en Y y 2.5 en Z

# ─────────────────────────────────────────────
# 8. ILUMINACIÓN
# ─────────────────────────────────────────────
# Sol principal
bpy.ops.object.light_add(type='SUN', location=(20, -15, 25))
sun = bpy.context.active_object
sun.name = "Sol"
sun.data.energy = 4.0
sun.data.angle  = math.radians(3)
sun.rotation_euler = (math.radians(45), 0, math.radians(30))

# Fill light (luz de relleno suave desde abajo-frente)
bpy.ops.object.light_add(type='AREA', location=(5, -6, 1))
fill = bpy.context.active_object
fill.name = "Fill"
fill.data.energy = 800
fill.data.size   = 12
fill.rotation_euler = (math.radians(60), 0, 0)

# Rim light (borde azul desde atrás para estilo AI Warehouse)
bpy.ops.object.light_add(type='SPOT', location=(0, 10, 5))
rim = bpy.context.active_object
rim.name = "Rim"
rim.data.energy = 2000
rim.data.color  = (0.3, 0.6, 1.0)
rim.data.spot_size = math.radians(60)
rim.rotation_euler = (math.radians(120), 0, math.radians(180))

# ─────────────────────────────────────────────
# 9. FONDO (mundo negro con niebla de ambiente)
# ─────────────────────────────────────────────
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value   = (0.01, 0.01, 0.03, 1.0)
    bg_node.inputs["Strength"].default_value = 0.2

# ─────────────────────────────────────────────
# 10. CONFIGURACIÓN DE RENDER
# ─────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine              = 'CYCLES'
scene.cycles.samples             = 128
scene.cycles.use_denoising       = True
scene.render.resolution_x        = 1920
scene.render.resolution_y        = 1080
scene.render.fps                 = 60
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format       = 'MPEG4'
scene.render.ffmpeg.codec        = 'H264'
scene.render.filepath            = r"C:\Users\wenas\OneDrive\Escritorio\Ia\sonso_render.mp4"

# Motion blur
scene.render.use_motion_blur     = True
scene.render.motion_blur_shutter = 0.5

print(f"[Sonso] ✅ Escena lista: {n_frames} frames | {n_frames/60:.1f} segundos")
print(f"[Sonso] Presiona Spacebar para previsualizar, Ctrl+F12 para renderizar.")
