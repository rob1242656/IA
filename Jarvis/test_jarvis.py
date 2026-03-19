"""
JARVIS V8 — Test de dependencias y modulos
============================================
Ejecutar: python test_jarvis.py
"""

def test():
    results = []

    # Core dependencies
    core = {
        "flask": "Flask web server",
        "flask_socketio": "Flask-SocketIO (websockets)",
        "flask_cors": "Flask-CORS",
        "psutil": "System monitoring",
        "requests": "HTTP requests",
        "anthropic": "Anthropic API (Claude)",
        "dotenv": "python-dotenv (.env loader)",
    }
    for module, desc in core.items():
        try:
            __import__(module)
            results.append(f"  ✅ {desc}")
        except ImportError:
            results.append(f"  ❌ {desc} — pip install {module}")

    # Optional: Voice
    voice = {
        "speech_recognition": "Voice input (ambient mode)",
        "pyttsx3": "Voice output (TTS)",
        "pyaudio": "Audio I/O (mic)",
    }
    for module, desc in voice.items():
        try:
            __import__(module)
            results.append(f"  ✅ {desc}")
        except ImportError:
            results.append(f"  ⚠️  {desc} [opcional] — pip install {module}")

    # Optional: Automation
    auto = {
        "pyautogui": "Desktop automation",
    }
    for module, desc in auto.items():
        try:
            __import__(module)
            results.append(f"  ✅ {desc}")
        except ImportError:
            results.append(f"  ⚠️  {desc} [opcional] — pip install {module}")

    # Windows-specific
    import platform
    if platform.system() == "Windows":
        try:
            import win32gui  # noqa: F401
            results.append("  ✅ pywin32 (Windows desktop control)")
        except ImportError:
            results.append("  ⚠️  pywin32 [opcional] — pip install pywin32")

    # Module structure check
    results.append("")
    results.append("  MODULOS JARVIS V8:")
    for mod in ["brain", "ambient", "server"]:
        try:
            __import__(mod)
            results.append(f"  ✅ {mod}.py")
        except ImportError as e:
            results.append(f"  ❌ {mod}.py — {e}")

    # .env check
    from pathlib import Path
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        results.append("  ✅ .env encontrado")
    else:
        results.append("  ❌ .env no encontrado — crea uno con ANTHROPIC_API_KEY=...")

    # Templates check
    hud_path = Path(__file__).parent / "templates" / "hud.html"
    if hud_path.exists():
        results.append("  ✅ templates/hud.html encontrado")
    else:
        results.append("  ❌ templates/hud.html no encontrado")

    # Print results
    print("\n" + "=" * 50)
    print("  JARVIS V8 — TEST DE DEPENDENCIAS")
    print("=" * 50 + "\n")

    for r in results:
        print(r)

    print("\n" + "=" * 50)

    missing = [r for r in results if "❌" in r]
    if missing:
        print(f"\n  ⚠️  Faltan {len(missing)} componentes obligatorios")
    else:
        print("\n  ✅ TODO LISTO — ejecuta: python Jarvis.py")

    print()


if __name__ == "__main__":
    test()
