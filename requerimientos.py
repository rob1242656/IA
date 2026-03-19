"""
requerimientos.py — Verifica e instala las dependencias del proyecto Sonso IA
==============================================================================
Uso:
    python requerimientos.py

Tres estados posibles por librería:
  ✅  Instalada y funciona correctamente
  ⚠️  Instalada pero no carga (DLL rota / fallo de import)
  ❌  No instalada en el entorno actual
"""

import sys
import subprocess
import importlib.util

# ─────────────────────────────────────────────
# LIBRERÍAS REQUERIDAS
# ─────────────────────────────────────────────
# (nombre_pip, nombre_import, descripcion)
REQUERIMIENTOS = [
    ("gymnasium",         "gymnasium",         "Entornos de RL (ambiente de Sonso)"),
    ("numpy",             "numpy",             "Operaciones numéricas y arrays"),
    ("pymunk",            "pymunk",            "Motor de física 2D (simulación del robot)"),
    ("pygame",            "pygame",            "Renderizado visual de la simulación"),
    ("torch",             "torch",             "PyTorch — backend de redes neuronales"),
    ("stable-baselines3", "stable_baselines3", "Algoritmos SAC/PPO para entrenar al agente"),
    ("tensorboard",       "tensorboard",       "Monitoreo de entrenamiento en tiempo real"),
]

print("=" * 65)
print("  SONSO IA — Verificador de Requerimientos")
print("=" * 65)
print(f"  Python: {sys.version.split()[0]}  |  Plataforma: {sys.platform}\n")

faltantes = []   # no instalados (pip install los puede arreglar)
rotos     = []   # instalados pero no cargan (DLL u otro problema de sistema)

for pip_name, import_name, descripcion in REQUERIMIENTOS:
    # Paso 1: ¿está instalado? (sin importar, solo busca el paquete en el entorno)
    spec = importlib.util.find_spec(import_name)
    if spec is None:
        print(f"  ❌  {pip_name:<22} {'NO INSTALADO':<16}  {descripcion}")
        faltantes.append(pip_name)
        continue

    # Paso 2: está instalado — intentar importar para ver si carga
    try:
        mod     = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "?")
        print(f"  ✅  {pip_name:<22} v{version:<15}  {descripcion}")
    except (ImportError, OSError) as e:
        # Está instalado pero falla al cargar (DLL rota, extension .pyd rota, etc.)
        print(f"  ⚠️  {pip_name:<22} {'INSTALADO/ROTO':<16}  {descripcion}")
        # Mostrar solo la primera línea del error para no llenar la pantalla
        primera_linea = str(e).split('\n')[0][:90]
        print(f"       → {primera_linea}")
        rotos.append(pip_name)

# ─────────────────────────────────────────────
# NOTA bpy (Blender — no es pip)
# ─────────────────────────────────────────────
print()
print("  ℹ️   bpy (Blender Python API)  —  blender_sonso.py")
print("       No se instala con pip. Viene incluido dentro de Blender.")
print("       Solo funciona cuando corres blender_sonso.py DESDE Blender.")

# ─────────────────────────────────────────────
# DIAGNÓSTICO Y SOLUCIONES
# ─────────────────────────────────────────────
print()
print("─" * 65)

# Paquetes rotos
if rotos:
    print(f"\n  ⚠️  {len(rotos)} paquete(s) instalado(s) pero que no cargan:")
    for pkg in rotos:
        print(f"       • {pkg}")
    print()
    print("  Causa: DLL de Windows faltante (muy común con torch en AMD/CPU).")
    print()

    if "torch" in rotos:
        print("  ── SOLUCIÓN para torch (AMD GPU en Windows = CPU-only) ──")
        print()
        print("    pip uninstall torch torchvision -y")
        print("    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu")
        print()
        print("  Nota: PyTorch con AMD GPU solo funciona en Linux (ROCm).")
        print("        CPU-only es suficiente para entrenar a Sonso IA.")
        print()

    otros_rotos = [p for p in rotos if p != "torch"]
    if otros_rotos:
        print("  ── SOLUCIÓN para otros paquetes rotos ──")
        print()
        print("  Prueba reinstalarlos:")
        print(f"    pip install --force-reinstall {' '.join(otros_rotos)}")
        print()
        print("  Si sigue fallando, instala Visual C++ Redistributable:")
        print("    https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print()

# Paquetes faltantes
if faltantes:
    print(f"\n  ❌  {len(faltantes)} paquete(s) no instalado(s):")
    print()
    cmd = "pip install " + " ".join(faltantes)
    print(f"    {cmd}")
    print()
    respuesta = input("  ¿Instalar ahora? [s/N]: ").strip().lower()
    if respuesta == "s":
        print()
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + faltantes)
        print("\n  Vuelve a correr requerimientos.py para verificar.")
    else:
        print("  Corre el comando de arriba manualmente cuando quieras.")

# Todo bien
if not faltantes and not rotos:
    print("\n  ✅ Todo OK. El proyecto está listo para correr.\n")
    print("  PASOS DE EJECUCIÓN:")
    print()
    print("  1. Entrenar (si no tienes modelo):")
    print("       python main_ppo.py")
    print()
    print("  2. Exportar trayectoria del modelo entrenado:")
    print("       python enjoy_export.py")
    print("       → genera: sonso_trajectory.json")
    print()
    print("  3. Visualizar en Blender:")
    print("       a) Abrir Blender → pestaña 'Scripting'")
    print("       b) Abrir blender_sonso.py → Run Script")
    print("       c) Spacebar = previsualizar | Ctrl+F12 = renderizar video")
    print("       → genera: sonso_render.mp4")

print()
print("=" * 65)
