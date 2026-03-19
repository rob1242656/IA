"""
JARVIS V8 ULTIMATE — AMBIENT AWARENESS EDITION
================================================
Entry point. Carga .env, inicializa subsistemas, maneja shutdown.

Ejecutar:
  python Jarvis.py
  -> http://localhost:5000

Dependencias:
  pip install -r requirements.txt
"""

import os
import sys
import signal
import atexit
import platform

# ── Cargar variables de entorno desde .env ────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv no instalado. Cargando desde variables del sistema.")
    print("   Instala con: pip install python-dotenv")

# ── Verificar dependencias core ──────────────────────
try:
    import flask                    # noqa: F401
    import flask_socketio           # noqa: F401
    import flask_cors               # noqa: F401
    import psutil                   # noqa: F401
    import requests                 # noqa: F401
    import anthropic                # noqa: F401
except ImportError as e:
    print(f"\n❌ Dependencia faltante: {e}")
    print("   Instala todas con: pip install -r requirements.txt")
    sys.exit(1)

# ── Banner ───────────────────────────────────────────
OS = platform.system()
print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗  V8 ULTIMATE      ║
║  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝  AMBIENT AWARE    ║
║  ██║███████║██████╔╝██║   ██║██║███████╗                    ║
║  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║  OS: {OS:<12}   ║
║  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║                    ║
║  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝                  ║
╚══════════════════════════════════════════════════════════════╝
""")

# ── Importar modulos de JARVIS ───────────────────────
from server import app, socketio, init_app, shutdown_app
from ambient import VOICE_OK


# ── Shutdown limpio ──────────────────────────────────
atexit.register(shutdown_app)

def _signal_handler(sig, frame):
    """Maneja Ctrl+C limpiamente."""
    shutdown_app()
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════
def main():
    # Obtener API key
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        key = input("🔑 API key Anthropic: ").strip()
        if not key:
            print("❌ Se necesita una API key de Anthropic.")
            sys.exit(1)
        os.environ["ANTHROPIC_API_KEY"] = key

    # Actualizar Config con la key
    from brain import Config
    Config.API_KEY = key

    # Inicializar todos los subsistemas
    init_app(key)

    # Info de arranque
    print("\n" + "=" * 56)
    print("  ✅  JARVIS V8 ULTIMATE — AMBIENT AWARENESS")
    print("=" * 56)
    print(f"  🌐  http://localhost:5000")
    print(f"  🎤  Ambient voice: {'✅ Activo' if VOICE_OK else '❌ pip install SpeechRecognition pyttsx3 pyaudio'}")
    print(f"  🖥️   Desktop control: ✅ ({OS})")
    print(f"  🔔  Proactive monitor: ✅")
    print(f"  📊  Stats cache: ✅ (push cada 5s, zero-blocking)")
    print()
    print("  COMANDOS DE VOZ:")
    print('  🎤 "silencio"      → minimiza TODO')
    print('  🎤 "despeja"       → minimiza TODO')
    print('  🎤 "escritorio"    → minimiza TODO')
    print('  🎤 "modo zen"      → minimiza TODO')
    print('  🎤 "restaura"      → restaura ventanas')
    print("=" * 56)
    print("  Ctrl+C para detener\n")

    # Arrancar servidor
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
