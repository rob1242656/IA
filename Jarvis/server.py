"""
JARVIS V8 — Server Module
===========================
Flask app, SocketIO, rutas y push helper.
"""

import secrets
import os

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from brain import JarvisV8, StatsCache
from ambient import AmbientListener, ProactiveMonitor, TTSWorker, VOICE_OK


# ════════════════════════════════════════════════════════
# FLASK APP
# ════════════════════════════════════════════════════════
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", secrets.token_hex(32))
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Instancias globales (inicializadas en init_app)
brain: JarvisV8 = None          # type: ignore
ambient: AmbientListener = None  # type: ignore
monitor: ProactiveMonitor = None # type: ignore
tts: TTSWorker = None            # type: ignore
stats_cache: StatsCache = None   # type: ignore


def push(event: str, data: dict):
    """Helper para emitir WebSocket desde cualquier thread."""
    socketio.emit(event, data)


# ════════════════════════════════════════════════════════
# INIT — Conecta todos los componentes
# ════════════════════════════════════════════════════════
def init_app(api_key: str):
    """Inicializa todos los subsistemas de JARVIS."""
    global brain, ambient, monitor, tts, stats_cache

    print("\n⚙️  Inicializando sistemas V8...")

    # 1. Stats cache (un solo thread para todas las stats)
    stats_cache = StatsCache(interval=5.0, push_callback=push)
    stats_cache.start()

    # 2. Brain (cerebro principal)
    brain = JarvisV8(api_key=api_key, stats_cache=stats_cache, push_callback=push)

    # 3. TTS worker (thread dedicado para voz)
    tts = None
    if VOICE_OK:
        tts = TTSWorker()

    # 4. Proactive monitor
    monitor = ProactiveMonitor(stats_cache=stats_cache, push_callback=push)
    monitor.start()

    # 5. Ambient listener
    ambient = AmbientListener(
        desktop=brain.desktop,
        tts=tts,
        on_command=brain.process,
        push=push
    )
    ambient.start()


def shutdown_app():
    """Apaga todos los subsistemas limpiamente."""
    print("\n🔌 Apagando JARVIS...")
    if monitor:
        monitor.stop()
    if ambient:
        ambient.stop()
    if tts:
        tts.shutdown()
    if stats_cache:
        stats_cache.stop()
    if brain:
        brain.integs.close()
    print("👋 Goodbye, sir.")


# ════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("hud.html")


# ════════════════════════════════════════════════════════
# SOCKET EVENTS
# ════════════════════════════════════════════════════════
@socketio.on("connect")
def on_connect():
    emit("status", {"ok": True})


@socketio.on("greeting")
def on_greeting():
    if brain:
        emit("greeting", {"text": brain.greeting()})


@socketio.on("msg")
def on_msg(data):
    text = (data.get("text") or "").strip()
    if not text or not brain:
        return
    result = brain.process(text)
    emit("response", result)
    if result.get("type") == "weather":
        emit("weather_data", result.get("data", {}))
    elif result.get("type") == "news":
        emit("news_data", result.get("data", []))


@socketio.on("stats_req")
def on_stats():
    """Fallback por si el cliente aun pide stats manualmente."""
    if stats_cache:
        emit("stats", stats_cache.get())


@socketio.on("load_news")
def on_news():
    if brain:
        emit("news_data", brain.integs.news())


@socketio.on("load_weather")
def on_weather():
    if brain:
        emit("weather_data", brain.integs.weather())


@socketio.on("reminder_check")
def on_reminders():
    if brain:
        for t in brain.memory.pop_due():
            emit("reminder", {"text": t})
