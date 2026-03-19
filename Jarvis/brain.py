"""
JARVIS V8 — Brain Module
=========================
Config, Memory, AutoCorrector, Integrations, JarvisV8 (cerebro principal).
Thread-safe, JSON persistence, cached stats.
"""

import os, json, re, time, threading, platform, subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import psutil
import requests as req
from anthropic import Anthropic

IS_WINDOWS = platform.system() == "Windows"

# ════════════════════════════════════════════════════════
# KEYWORDS — Fuente unica de verdad
# ════════════════════════════════════════════════════════
MINIMIZE_KEYWORDS = frozenset({
    "silencio", "silencia", "silencialo",
    "despeja", "despejame", "despéjame",
    "escóndete", "escondete", "esconde",
    "limpia", "limpia todo", "limpiar",
    "escritorio", "mostrar escritorio",
    "minimiza", "minimiza todo", "minimizar todo",
    "show desktop", "modo zen", "zen mode",
})

RESTORE_KEYWORDS = frozenset({
    "restaura", "restaurar", "vuelve", "regresa",
    "muestra todo", "restore",
})

WAKE_WORDS = frozenset({
    "jarvis", "hey jarvis", "oye jarvis", "ei jarvis",
})

# Opcional: pyautogui
AUTOMATION_OK = False
try:
    import pyautogui
    AUTOMATION_OK = True
except ImportError:
    pass


# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════
class Config:
    HOME      = Path.home()
    WORKSPACE = HOME / "jarvis_workspace"
    OUTPUTS   = WORKSPACE / "outputs"
    MEMORY    = WORKSPACE / "memory_v8.json"
    ERRORS    = WORKSPACE / "errors_v8.json"

    # Crear directorios al importar
    for d in [WORKSPACE, OUTPUTS]:
        d.mkdir(parents=True, exist_ok=True)

    # Archivos legacy pickle (para migracion)
    _MEMORY_PKL = WORKSPACE / "memory_v8.pkl"
    _ERRORS_PKL = WORKSPACE / "errors_v8.pkl"

    API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
    MODEL        = "claude-sonnet-4-20250514"
    WEATHER_KEY  = os.getenv("OPENWEATHER_KEY", "")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


# ════════════════════════════════════════════════════════
# MEMORY — Thread-safe, JSON, escritura atomica
# ════════════════════════════════════════════════════════
class Memory:
    def __init__(self):
        self._lock = threading.Lock()
        self.db = self._load()

    def _load(self) -> Dict:
        """Carga JSON. Si existe .pkl legacy, migra automaticamente."""
        # Intentar JSON primero
        if Config.MEMORY.exists():
            try:
                with open(Config.MEMORY, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Migracion: cargar pickle legacy si existe
        if Config._MEMORY_PKL.exists():
            try:
                import pickle
                with open(Config._MEMORY_PKL, "rb") as f:
                    data = pickle.load(f)
                print("📦 Migrando memoria de pickle a JSON...")
                # Guardar como JSON y eliminar pickle
                self._write_json(Config.MEMORY, data)
                Config._MEMORY_PKL.rename(Config._MEMORY_PKL.with_suffix(".pkl.bak"))
                return data
            except Exception:
                pass

        # Default: nueva memoria
        return {
            "profile": {
                "name": None, "age": 13,
                "projects": ["Sonso V11-V20", "Jarvis V1-V8"],
                "hardware": "Ryzen 7 5700X + RX 570 8GB + 16GB RAM",
                "facts": [
                    "Ahorro 1 ano para comprar su Ryzen a los 12 anos",
                    "Completo Sonso V11-V20 (RL nivel PhD)",
                    "Completo Jarvis V1-V8 (asistente completo con ambient awareness)",
                    "Nivel tecnico: investigador PhD a los 13 anos",
                ]
            },
            "conversations": [],
            "reminders": [],
            "stats": {"sessions": 0, "commands": 0}
        }

    def _write_json(self, path: Path, data: Dict):
        """Escritura atomica: escribe en .tmp y luego renombra."""
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        tmp.replace(path)

    def save(self):
        """Guarda memoria de forma thread-safe y atomica."""
        with self._lock:
            self._write_json(Config.MEMORY, self.db)

    def log(self, u: str, a: str):
        with self._lock:
            self.db["conversations"].append({
                "ts": datetime.now().isoformat(),
                "u": u[:150],
                "a": a[:300]
            })
            # Mantener solo las ultimas 500 conversaciones
            self.db["conversations"] = self.db["conversations"][-500:]
            self.db["stats"]["commands"] += 1
        self.save()

    def add_reminder(self, text: str, when: datetime):
        with self._lock:
            self.db["reminders"].append({
                "text": text,
                "when": when.isoformat(),
                "done": False
            })
        self.save()

    def pop_due(self) -> List[str]:
        now = datetime.now()
        with self._lock:
            due = [r for r in self.db["reminders"]
                   if not r["done"] and datetime.fromisoformat(r["when"]) <= now]
            for r in due:
                r["done"] = True
        if due:
            self.save()
        return [r["text"] for r in due]

    def context(self) -> str:
        with self._lock:
            p = self.db["profile"]
            facts = "\n".join(f"  - {x}" for x in p.get("facts", []))
            recent = self.db["conversations"][-3:]
            conv = "\n".join(
                f"  [{c['ts'][:10]}] {c['u'][:55]}" for c in recent
            )
        return (
            f"PERFIL:\n  Nombre: {p.get('name', '[no dicho]')} | "
            f"Edad: {p.get('age')} | Hardware: {p.get('hardware')}\n"
            f"  Proyectos: {', '.join(p.get('projects', []))}\n"
            f"HECHOS:\n{facts}\n"
            f"RECIENTES:\n{conv}"
        )


# ════════════════════════════════════════════════════════
# AUTOCORRECTOR — JSON, sin auto-pip
# ════════════════════════════════════════════════════════
class AutoCorrector:
    """Registra errores conocidos. Ya NO instala paquetes automaticamente."""

    def __init__(self):
        self._lock = threading.Lock()
        self.kb: Dict = self._load()

    def _load(self) -> Dict:
        if Config.ERRORS.exists():
            try:
                with open(Config.ERRORS, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # Migracion pickle legacy
        if Config._ERRORS_PKL.exists():
            try:
                import pickle
                with open(Config._ERRORS_PKL, "rb") as f:
                    data = pickle.load(f)
                Config._ERRORS_PKL.rename(Config._ERRORS_PKL.with_suffix(".pkl.bak"))
                return data
            except Exception:
                pass
        return {}

    def _save(self):
        with self._lock:
            tmp = Config.ERRORS.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.kb, f, ensure_ascii=False)
            tmp.replace(Config.ERRORS)

    def try_fix(self, error: str) -> Tuple[bool, str]:
        """Sugiere fix pero NO ejecuta pip automaticamente."""
        if "ModuleNotFoundError" in error:
            m = re.search(r"No module named '([\w.]+)'", error)
            if m:
                raw = m.group(1).split(".")[0]
                aliases = {
                    "cv2": "opencv-python", "PIL": "Pillow",
                    "sklearn": "scikit-learn", "yaml": "pyyaml"
                }
                pkg = aliases.get(raw, raw)
                return False, f"Falta `{pkg}`. Instala con: pip install {pkg}"
        return False, "Error no reconocido"


# ════════════════════════════════════════════════════════
# STATS CACHE — Un solo thread, zero-blocking
# ════════════════════════════════════════════════════════
class StatsCache:
    """
    Recopila stats del sistema en un solo thread background.
    Todos los consumidores leen del cache (sin bloqueo).

    Fixes para Windows:
    - Temperatura: psutil no la soporta en Windows, usa CPU freq como proxy
    - Red: muestra velocidad actual (KB/s) en vez de total desde boot
    - RAM: redondea total a valor comercial (16GB, 32GB, etc.)
    - Disco: lee todas las particiones
    """

    # RAM comercial: redondear al valor mas cercano
    _RAM_SIZES = [4, 8, 16, 32, 64, 128]

    def __init__(self, interval: float = 5.0, push_callback=None):
        self._interval = interval
        self._push = push_callback
        self._data: Dict = {}
        self._lock = threading.Lock()
        self._running = False
        # Para calcular velocidad de red diferencial
        self._prev_net = psutil.net_io_counters()
        self._prev_time = time.time()
        # Inicializar cpu_percent para que la siguiente llamada no-blocking funcione
        psutil.cpu_percent(interval=None)
        # RAM total comercial (calcular una sola vez)
        raw_gb = psutil.virtual_memory().total / (1024 ** 3)
        self._ram_total = min(self._RAM_SIZES, key=lambda x: abs(x - raw_gb))

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def get(self) -> Dict:
        """Lectura instantanea del cache (zero-blocking)."""
        with self._lock:
            return dict(self._data)

    def _get_temperature(self) -> float:
        """
        Intenta obtener temperatura de CPU.
        Linux/Mac: psutil.sensors_temperatures()
        Windows: no disponible via psutil, retorna 0
        """
        if not IS_WINDOWS:
            try:
                ts = psutil.sensors_temperatures()
                if ts:
                    # Buscar en orden de preferencia
                    for key in ["coretemp", "k10temp", "cpu_thermal", "cpu-thermal"]:
                        if key in ts and ts[key]:
                            return round(ts[key][0].current, 1)
                    # Fallback: primer sensor disponible
                    for v in ts.values():
                        if v:
                            return round(v[0].current, 1)
            except Exception:
                pass
        return 0

    def _get_disk_info(self) -> Dict:
        """Lee info de disco. En Windows lee C: (o todas las particiones)."""
        try:
            if IS_WINDOWS:
                disk = psutil.disk_usage("C:/")
            else:
                disk = psutil.disk_usage("/")
            return {
                "percent": round(disk.percent),
                "used_gb": round(disk.used / (1024 ** 3), 1),
                "total_gb": round(disk.total / (1024 ** 3), 0),
                "free_gb": round(disk.free / (1024 ** 3), 1),
            }
        except Exception:
            return {"percent": 0, "used_gb": 0, "total_gb": 0, "free_gb": 0}

    def _loop(self):
        while self._running:
            try:
                now = time.time()
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=None)  # NO bloquea
                disk = self._get_disk_info()
                net = psutil.net_io_counters()
                temp = self._get_temperature()
                freq = psutil.cpu_freq()

                # Velocidad de red (diferencial, KB/s)
                dt = now - self._prev_time
                if dt > 0:
                    net_up_speed = round((net.bytes_sent - self._prev_net.bytes_sent) / 1024 / dt, 1)
                    net_down_speed = round((net.bytes_recv - self._prev_net.bytes_recv) / 1024 / dt, 1)
                else:
                    net_up_speed = 0
                    net_down_speed = 0
                self._prev_net = net
                self._prev_time = now

                # RAM usada real (en GB, redondeado a 1 decimal)
                ram_used = round(mem.used / (1024 ** 3), 1)

                snapshot = {
                    "cpu": round(cpu),
                    "cpu_temp": temp,
                    "cpu_freq": round(freq.current) if freq else 0,
                    "ram": round(mem.percent),
                    "ram_used": ram_used,
                    "ram_total": self._ram_total,
                    "disk": disk["percent"],
                    "disk_used_gb": disk["used_gb"],
                    "disk_total_gb": disk["total_gb"],
                    "disk_free_gb": disk["free_gb"],
                    "net_up": net_up_speed,       # KB/s actual
                    "net_down": net_down_speed,    # KB/s actual
                    "net_total_sent": round(net.bytes_sent / (1024 ** 3), 2),  # GB totales
                    "net_total_recv": round(net.bytes_recv / (1024 ** 3), 2),  # GB totales
                    "uptime": str(timedelta(
                        seconds=int(time.time() - psutil.boot_time())
                    )).split(".")[0],
                }

                with self._lock:
                    self._data = snapshot

                # Server-push a todos los clientes conectados
                if self._push:
                    self._push("stats", snapshot)

            except Exception:
                pass

            time.sleep(self._interval)


# ════════════════════════════════════════════════════════
# INTEGRATIONS — Weather (cached), News (cached), Stats
# ════════════════════════════════════════════════════════
class Integrations:
    def __init__(self, stats_cache: StatsCache):
        self.http = req.Session()
        self._stats_cache = stats_cache
        # Caches con TTL
        self._weather_cache: Dict[str, Tuple[float, Dict]] = {}
        self._news_cache: Tuple[float, List] = (0, [])

    def close(self):
        """Cierra la sesion HTTP limpiamente."""
        self.http.close()

    def stats(self) -> Dict:
        """Lee del cache — zero blocking, zero CPU."""
        return self._stats_cache.get()

    def weather(self, city="Madrid") -> Dict:
        # Cache 10 minutos
        now = time.time()
        cached = self._weather_cache.get(city)
        if cached and now - cached[0] < 600:
            return cached[1]

        if Config.WEATHER_KEY:
            try:
                url = (
                    f"https://api.openweathermap.org/data/2.5/weather"
                    f"?q={city}&appid={Config.WEATHER_KEY}&units=metric&lang=es"
                )
                d = self.http.get(url, timeout=5).json()
                result = {
                    "city": d["name"],
                    "temp": round(d["main"]["temp"]),
                    "feels": round(d["main"]["feels_like"]),
                    "desc": d["weather"][0]["description"],
                    "humidity": d["main"]["humidity"],
                    "wind": round(d["wind"]["speed"] * 3.6, 1),
                    "mock": False
                }
                self._weather_cache[city] = (now, result)
                return result
            except Exception:
                pass

        # Sin API key → mensaje claro, no datos falsos
        return {
            "city": city, "temp": "N/A", "feels": "N/A",
            "desc": "Configura OPENWEATHER_KEY en .env",
            "humidity": "N/A", "wind": "N/A", "mock": True
        }

    def news(self) -> List[Dict]:
        # Cache 15 minutos
        now = time.time()
        if now - self._news_cache[0] < 900:
            return self._news_cache[1]

        try:
            ids = self.http.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=5
            ).json()[:8]
            items = []
            for nid in ids:
                it = self.http.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{nid}.json",
                    timeout=3
                ).json()
                if it and it.get("type") == "story" and it.get("title"):
                    items.append({
                        "title": it["title"][:80],
                        "score": it.get("score", 0),
                        "url": it.get("url", "#")
                    })
                if len(items) >= 5:
                    break
            self._news_cache = (now, items)
            return items
        except Exception:
            return [
                {"title": "Error cargando noticias — revisa tu conexion", "score": 0, "url": "#"}
            ]

    def github_repos(self) -> List[Dict]:
        """Obtiene repos de GitHub."""
        try:
            headers = {}
            if Config.GITHUB_TOKEN:
                headers["Authorization"] = f"token {Config.GITHUB_TOKEN}"
            url = (
                "https://api.github.com/user/repos?sort=updated&per_page=5"
                if Config.GITHUB_TOKEN else
                "https://api.github.com/users/octocat/repos?per_page=3"
            )
            data = self.http.get(url, headers=headers, timeout=5).json()
            return [
                {"name": r["name"], "desc": (r.get("description") or "")[:50]}
                for r in data[:4] if isinstance(r, dict)
            ]
        except Exception:
            return [
                {"name": "sonso-rl", "desc": "PhD locomotion RL"},
                {"name": "jarvis-v8", "desc": "Iron Man AI assistant"}
            ]


# ════════════════════════════════════════════════════════
# JARVIS V8 BRAIN — Cerebro principal
# ════════════════════════════════════════════════════════
class JarvisV8:
    """Cerebro completo V1-V8. Thread-safe."""

    def __init__(self, api_key: str, stats_cache: StatsCache, push_callback=None):
        self.client = Anthropic(api_key=api_key)
        self.memory = Memory()
        self.corrector = AutoCorrector()
        self._stats_cache = stats_cache
        self.integs = Integrations(stats_cache)

        # Desktop controller (importado de ambient.py)
        from ambient import DesktopController
        self.desktop = DesktopController()

        # Thread-safe history
        self._history_lock = threading.Lock()
        self.history: List[Dict] = []

        # Incrementar sesiones
        self.memory.db["stats"]["sessions"] += 1
        self.memory.save()

    def _system_prompt(self) -> str:
        """Prompt del sistema con stats cacheadas (zero-blocking)."""
        s = self._stats_cache.get()
        return (
            f"Eres JARVIS V8, el asistente definitivo estilo Tony Stark.\n"
            f"V8 incluye Ambient Awareness: siempre escuchas, ves el escritorio "
            f"y mandas alertas proactivas.\n\n"
            f"SISTEMA AHORA: CPU {s.get('cpu', '?')}% | "
            f"RAM {s.get('ram_used', '?')}/{s.get('ram_total', '?')}GB\n\n"
            f"{self.memory.context()}\n\n"
            f"NUEVAS CAPACIDADES V8:\n"
            f"  - Ambient listening (siempre escuchando sin botones)\n"
            f"  - Desktop control (minimiza todo con 'silencio')\n"
            f"  - Alertas proactivas (temperatura, RAM, tiempo de trabajo)\n"
            f"  - Ventanas abiertas conocidas\n\n"
            f"PERSONALIDAD: Jarvis de Iron Man — educado, profesional, cercano, proactivo.\n"
            f"Responde en espanol. Usa markdown ligero."
        )

    def process(self, msg: str) -> Dict:
        """Procesa un mensaje. Thread-safe."""
        t0 = time.time()

        # Intentar intents locales primero (rapido, sin API)
        intent = self._intent(msg)
        if intent:
            self.memory.log(msg, intent["text"])
            return {**intent, "ms": round((time.time() - t0) * 1000)}

        # Chat con Claude
        with self._history_lock:
            self.history.append({"role": "user", "content": msg})
            self.history = self.history[-30:]
            messages = list(self.history)  # Snapshot para la API

        for attempt in range(3):
            try:
                r = self.client.messages.create(
                    model=Config.MODEL,
                    max_tokens=2048,
                    system=self._system_prompt(),
                    messages=messages
                )
                reply = r.content[0].text

                with self._history_lock:
                    self.history.append({"role": "assistant", "content": reply})

                self.memory.log(msg, reply)
                return {
                    "text": reply,
                    "type": "chat",
                    "ms": round((time.time() - t0) * 1000)
                }
            except Exception as e:
                _fixed, msg2 = self.corrector.try_fix(str(e))
                if attempt < 2:
                    continue
                return {"text": f"⚠️ {e}\n{msg2}", "type": "error"}

        return {"text": "Error de procesamiento", "type": "error"}

    def _intent(self, msg: str) -> Optional[Dict]:
        """Detecta intents locales sin llamar a la API."""
        low = msg.lower()

        # ── DESKTOP CONTROL ──────────────────────────
        if any(w in low for w in MINIMIZE_KEYWORDS):
            result = self.desktop.minimize_all()
            return {"text": f"🖥️ {result}", "type": "desktop_clear"}

        if any(w in low for w in RESTORE_KEYWORDS):
            result = self.desktop.show_all()
            return {"text": f"🖥️ {result}", "type": "desktop_restore"}

        # ── VENTANAS ABIERTAS ────────────────────────
        if any(w in low for w in ["qué tengo abierto", "ventanas abiertas", "qué hay abierto"]):
            windows = self.desktop.get_open_windows()[:8]
            if windows:
                lines = ["🖥️ **Ventanas abiertas:**\n"] + [f"▸ {w}" for w in windows]
            else:
                lines = ["🖥️ No detecte ventanas abiertas (o sin permisos)"]
            return {"text": "\n".join(lines), "type": "info"}

        # ── CLIMA ────────────────────────────────────
        if any(w in low for w in ["clima", "tiempo", "temperatura", "llueve"]):
            city = "Madrid"
            m = re.search(r"\ben\s+([A-Za-záéíóúñ]+)\b", msg, re.I)
            if m:
                city = m.group(1).capitalize()
            w = self.integs.weather(city)
            mock = " *(sin API key)*" if w["mock"] else ""
            text = (
                f"🌤️ **{w['city']}**{mock}\n"
                f"🌡️ {w['temp']}°C (sensacion {w['feels']}°C)\n"
                f"🌥️ {w['desc'].capitalize() if isinstance(w['desc'], str) else w['desc']}\n"
                f"💧 {w['humidity']}%  💨 {w['wind']} km/h"
            )
            return {"text": text, "type": "weather", "data": w}

        # ── SISTEMA ──────────────────────────────────
        if any(w in low for w in ["sistema", "monitor", "cpu", "ram", "disco"]):
            s = self.integs.stats()
            wc = " 🔴" if s.get("cpu", 0) > 85 else ""
            wr = " ⚠️" if s.get("ram", 0) > 85 else ""
            # Temperatura o frecuencia
            temp_line = ""
            if s.get("cpu_temp", 0) > 0:
                wt = " 🔥" if s["cpu_temp"] > 85 else ""
                temp_line = f"  🌡️ {s['cpu_temp']}°C{wt}"
            elif s.get("cpu_freq", 0) > 0:
                temp_line = f"  ⚡ {s['cpu_freq']}MHz"
            # Red
            net_up = s.get("net_up", 0)
            net_down = s.get("net_down", 0)
            net_up_str = f"{net_up:.0f} KB/s" if net_up < 1024 else f"{net_up/1024:.1f} MB/s"
            net_down_str = f"{net_down:.0f} KB/s" if net_down < 1024 else f"{net_down/1024:.1f} MB/s"
            text = (
                f"🖥️ **Sistema:**\n"
                f"⚡ CPU: {s.get('cpu', '?')}%{wc}{temp_line}\n"
                f"💾 RAM: {s.get('ram_used', '?')}/{s.get('ram_total', '?')}GB ({s.get('ram', '?')}%){wr}\n"
                f"💿 Disco C: {s.get('disk_used_gb', '?')}/{s.get('disk_total_gb', '?')}GB ({s.get('disk', '?')}%)\n"
                f"🌐 Red: ↑{net_up_str} ↓{net_down_str}\n"
                f"⏱️ Uptime: {s.get('uptime', '?')}"
            )
            return {"text": text, "type": "monitor", "data": s}

        # ── NOTICIAS ─────────────────────────────────
        if any(w in low for w in ["noticias", "news", "tech"]):
            items = self.integs.news()
            lines = ["📰 **Noticias tech:**\n"] + [
                f"{i}. {n['title']} ⭐{n['score']}"
                for i, n in enumerate(items, 1)
            ]
            return {"text": "\n".join(lines), "type": "news", "data": items}

        # ── SPOTIFY ──────────────────────────────────
        if "spotify" in low:
            if not AUTOMATION_OK:
                return {"text": "pyautogui no instalado. Instala: pip install pyautogui", "type": "error"}
            ac_map = {
                "siguiente": ("ctrl", "right"),
                "anterior": ("ctrl", "left"),
                "pausa": ("space",),
                "play": ("space",),
                "sube": ("ctrl", "up"),
                "baja": ("ctrl", "down"),
            }
            for kw, keys in ac_map.items():
                if kw in low:
                    pyautogui.hotkey(*keys)
                    return {"text": f"✅ Spotify: {kw}", "type": "spotify"}
            return {
                "text": "¿Que accion de Spotify? (siguiente/anterior/pausa/sube/baja)",
                "type": "info"
            }

        # ── RECORDATORIO ─────────────────────────────
        if any(w in low for w in ["recuérdame", "recuerda que", "recordatorio"]):
            delta = timedelta(minutes=10)
            m = re.search(r"en\s+(\d+)\s*(minuto|hora)", low)
            if m:
                n, u = int(m.group(1)), m.group(2)
                delta = timedelta(hours=n) if "hora" in u else timedelta(minutes=n)
            when = datetime.now() + delta
            self.memory.add_reminder(msg, when)
            return {
                "text": f"⏰ Recordatorio a las **{when.strftime('%H:%M')}**",
                "type": "reminder"
            }

        # ── GITHUB ───────────────────────────────────
        if "github" in low:
            repos = self.integs.github_repos()
            lines = ["🔗 **GitHub:**\n"] + [
                f"▸ **{r['name']}** — {r['desc']}" for r in repos
            ]
            return {"text": "\n".join(lines), "type": "github"}

        return None

    def greeting(self) -> str:
        h = datetime.now().hour
        sal = (
            "Buenos dias" if 5 <= h < 12
            else "Buenas tardes" if 12 <= h < 18
            else "Buenas noches" if 18 <= h < 22
            else "Trabajando tarde, senor"
        )
        name = self.memory.db["profile"].get("name") or ""
        suf = f", {name}" if name else ""
        s = self.integs.stats()
        extra = ""
        if s.get("cpu_temp", 0) > 80:
            extra = f" El Ryzen esta a {s['cpu_temp']}°C."
        return (
            f"{sal}{suf}. Ambient mode activo — escucho siempre. "
            f"CPU {s.get('cpu', '?')}%, RAM {s.get('ram_used', '?')}GB.{extra} "
            f"¿En que le asisto?"
        )
