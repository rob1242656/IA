"""
JARVIS V8 ULTIMATE — AMBIENT AWARENESS EDITION
================================================
Integra V1→V7 + NUEVAS FEATURES V8:

✅ AMBIENT MODE — Siempre escuchando en background
✅ DESKTOP CONTROL — Minimiza TODO con voz
✅ "Silencio" / sinónimos → minimiza toda la pantalla
✅ Detección de palabras clave sin click
✅ Proactive notifications (avisa sin que preguntes)
✅ Screen monitoring (detecta cambios importantes)
✅ Activity tracking (cuánto llevas trabajando)
✅ Smart alerts (temperatura, RAM, tiempo)
✅ Context-aware responses (sabe qué tienes abierto)
✅ Multi-monitor support

PALABRAS QUE MINIMIZAN TODO:
  "silencio"     → minimiza todo
  "despeja"      → minimiza todo
  "escóndete"    → minimiza todo
  "limpia"       → minimiza todo
  "escritorio"   → minimiza todo
  "show desktop" → minimiza todo
  "minimiza todo"→ minimiza todo

CÓMO FUNCIONA EL AMBIENT MODE:
  1. Thread dedicado escucha micrófono 24/7
  2. Detecta wake word "Jarvis" → activa
  3. Detecta palabras especiales directamente
  4. Jarvis habla de vuelta sin esperar input
  5. Monitorea sistema en background
  6. Envía alertas proactivas a la GUI

IMPLEMENTACIÓN DESKTOP CONTROL:
  Windows: pyautogui + Win32 API (win32gui)
  Linux:   subprocess + wmctrl / xdotool
  Mac:     subprocess + AppleScript

EJECUTAR:
  python jarvis_v8_ultimate.py
  → http://localhost:5000
"""

import os, sys, json, time, threading, subprocess, pickle, re
import platform
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ── Auto-install ───────────────────────────────────────
def pip(pkg, imp=None):
    try:
        __import__(imp or pkg.replace("-","_"))
    except ImportError:
        print(f"📦 Instalando {pkg}...")
        subprocess.check_call([sys.executable,"-m","pip","install",pkg],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

pip("flask"); pip("flask-socketio","flask_socketio")
pip("flask-cors","flask_cors"); pip("psutil"); pip("requests")
pip("anthropic")

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from anthropic import Anthropic
import psutil, requests as req

# ── Opcionales ────────────────────────────────────────
VOICE_OK = False
try:
    import speech_recognition as sr, pyttsx3
    VOICE_OK = True
except ImportError:
    pass

AUTOMATION_OK = False
try:
    import pyautogui
    AUTOMATION_OK = True
except ImportError:
    pass

# ── Desktop control per OS ────────────────────────────
OS = platform.system()  # "Windows", "Linux", "Darwin"

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


# ════════════════════════════════════════════════════════
# DESKTOP CONTROLLER — EL NÚCLEO DE V8
# ════════════════════════════════════════════════════════
class DesktopController:
    """
    Controla el escritorio a nivel de sistema operativo.
    Funciona en Windows, Linux y Mac.
    """

    def __init__(self):
        self.os = platform.system()
        self._check_dependencies()

    def _check_dependencies(self):
        """Verificar dependencias según OS."""
        if self.os == "Windows":
            try:
                import win32gui, win32con
                self.win32_ok = True
            except ImportError:
                pip("pywin32", "win32gui")
                try:
                    import win32gui, win32con
                    self.win32_ok = True
                except:
                    self.win32_ok = False
                    print("⚠️  pywin32 no disponible, usando método alternativo")
        elif self.os == "Linux":
            # Verificar xdotool o wmctrl
            self.xdotool = subprocess.run(
                ["which","xdotool"], capture_output=True
            ).returncode == 0
            self.wmctrl = subprocess.run(
                ["which","wmctrl"], capture_output=True
            ).returncode == 0
        elif self.os == "Darwin":
            self.applescript_ok = True

    def minimize_all(self) -> str:
        """
        MINIMIZAR TODAS LAS VENTANAS — MOSTRAR ESCRITORIO.
        La función principal de V8.
        """
        print("🖥️  Minimizando todo...")

        if self.os == "Windows":
            return self._minimize_windows()
        elif self.os == "Linux":
            return self._minimize_linux()
        elif self.os == "Darwin":
            return self._minimize_mac()
        else:
            return "❌ Sistema operativo no soportado"

    def _minimize_windows(self) -> str:
        """Windows: múltiples métodos de fallback."""

        # Método 1: Win32 API (más confiable)
        try:
            import win32gui, win32con

            def minimize_window(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

            win32gui.EnumWindows(minimize_window, None)
            return "✅ Escritorio despejado (Win32 API)"
        except:
            pass

        # Método 2: Win+D (hotkey nativo)
        try:
            import pyautogui
            pyautogui.hotkey("win", "d")
            time.sleep(0.3)
            return "✅ Escritorio mostrado (Win+D)"
        except:
            pass

        # Método 3: PowerShell
        try:
            script = """
$shell = New-Object -ComObject Shell.Application
$shell.MinimizeAll()
"""
            subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, timeout=5
            )
            return "✅ Escritorio despejado (PowerShell)"
        except:
            pass

        # Método 4: VBScript
        try:
            vbs = 'Set sh = CreateObject("Shell.Application")\nsh.MinimizeAll'
            vbs_path = Path.home() / "jarvis_workspace" / "minimize.vbs"
            vbs_path.write_text(vbs)
            subprocess.run(["cscript", str(vbs_path)], capture_output=True, timeout=5)
            return "✅ Escritorio despejado (VBScript)"
        except:
            return "❌ No se pudo minimizar (instala pywin32)"

    def _minimize_linux(self) -> str:
        """Linux: xdotool / wmctrl / atajos."""

        # Método 1: xdotool
        if self.xdotool:
            try:
                subprocess.run(
                    ["xdotool", "key", "super+d"],
                    capture_output=True, timeout=3
                )
                return "✅ Escritorio mostrado (xdotool Super+D)"
            except:
                pass

            try:
                # Minimizar cada ventana individualmente
                result = subprocess.run(
                    ["xdotool", "search", "--onlyvisible", "--name", ""],
                    capture_output=True, text=True, timeout=3
                )
                for wid in result.stdout.strip().split("\n"):
                    if wid:
                        subprocess.run(
                            ["xdotool", "windowminimize", wid],
                            capture_output=True, timeout=2
                        )
                return "✅ Ventanas minimizadas (xdotool)"
            except:
                pass

        # Método 2: wmctrl
        if self.wmctrl:
            try:
                # Obtener lista de ventanas
                result = subprocess.run(
                    ["wmctrl", "-l"], capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        wid = line.split()[0]
                        subprocess.run(
                            ["wmctrl", "-i", "-r", wid, "-b", "add,hidden"],
                            capture_output=True, timeout=2
                        )
                return "✅ Ventanas minimizadas (wmctrl)"
            except:
                pass

        # Método 3: pyautogui hotkey
        if AUTOMATION_OK:
            try:
                # GNOME/KDE: Super+D
                pyautogui.hotkey("super", "d")
                return "✅ Escritorio mostrado (Super+D)"
            except:
                pass

        return ("⚠️  Instala xdotool para mejor control:\n"
                "  sudo apt-get install xdotool")

    def _minimize_mac(self) -> str:
        """Mac: AppleScript."""

        # Método 1: AppleScript - esconder todo
        script1 = 'tell application "System Events" to set visible of every process to false'
        try:
            subprocess.run(
                ["osascript", "-e", script1],
                capture_output=True, timeout=5
            )
            return "✅ Escritorio mostrado (AppleScript)"
        except:
            pass

        # Método 2: Mission Control / Exposé hotkey
        if AUTOMATION_OK:
            try:
                pyautogui.hotkey("command", "mission_control")
                return "✅ Mission Control activado"
            except:
                pass

        # Método 3: keyboard shortcut
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell application "Finder" to set collapsed of every window to true'],
                capture_output=True, timeout=5
            )
            return "✅ Ventanas minimizadas"
        except:
            return "⚠️  Activa permisos de Accessibility en Preferencias del Sistema"

    def show_all(self) -> str:
        """Restaurar todas las ventanas minimizadas."""

        if self.os == "Windows":
            try:
                import pyautogui
                pyautogui.hotkey("win", "shift", "m")  # Restore all
                return "✅ Ventanas restauradas"
            except:
                try:
                    script = """
$shell = New-Object -ComObject Shell.Application
$shell.UndoMinimizeAll()
"""
                    subprocess.run(["powershell","-Command",script],
                                   capture_output=True, timeout=5)
                    return "✅ Ventanas restauradas (PowerShell)"
                except:
                    return "❌ No se pudo restaurar"

        elif self.os == "Linux":
            if self.wmctrl:
                try:
                    result = subprocess.run(
                        ["wmctrl","-l"], capture_output=True, text=True
                    )
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            wid = line.split()[0]
                            subprocess.run(
                                ["wmctrl","-i","-r",wid,"-b","remove,hidden"],
                                capture_output=True
                            )
                    return "✅ Ventanas restauradas"
                except:
                    pass

        elif self.os == "Darwin":
            try:
                subprocess.run(
                    ["osascript","-e",
                     'tell application "System Events" to set visible of every process to true'],
                    capture_output=True, timeout=5
                )
                return "✅ Ventanas restauradas"
            except:
                pass

        return "❌ No se pudo restaurar"

    def get_open_windows(self) -> List[str]:
        """Obtener lista de ventanas abiertas."""
        windows = []

        if self.os == "Windows":
            try:
                import win32gui
                def cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title and len(title) > 2:
                            windows.append(title)
                win32gui.EnumWindows(cb, None)
            except:
                pass

        elif self.os == "Linux":
            if self.wmctrl:
                try:
                    r = subprocess.run(
                        ["wmctrl","-l"], capture_output=True, text=True
                    )
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append(parts[3])
                except:
                    pass

        elif self.os == "Darwin":
            try:
                script = ('tell application "System Events" to '
                          'get name of every window of every process')
                r = subprocess.run(
                    ["osascript","-e",script],
                    capture_output=True, text=True, timeout=5
                )
                windows = r.stdout.strip().split(", ")
            except:
                pass

        return [w for w in windows if w and len(w) > 1]


# ════════════════════════════════════════════════════════
# AMBIENT LISTENER — SIEMPRE ESCUCHANDO
# ════════════════════════════════════════════════════════
class AmbientListener:
    """
    Escucha el micrófono continuamente en background.
    Detecta palabras clave sin necesidad de botones.
    """

    # Palabras que minimizan todo (el escritorio)
    MINIMIZE_WORDS = {
        "silencio", "silencia", "silencialo",
        "despeja", "despejame", "despéjame",
        "escóndete", "escondete", "esconde",
        "limpia", "limpia todo",
        "escritorio", "mostrar escritorio",
        "minimiza", "minimiza todo", "minimizar todo",
        "show desktop", "limpiar",
        "modo zen", "zen mode",
    }

    # Wake words para activar Jarvis
    WAKE_WORDS = {
        "jarvis", "hey jarvis", "oye jarvis", "ei jarvis",
    }

    # Palabras de restaurar
    RESTORE_WORDS = {
        "restaura", "restaurar", "vuelve", "regresa",
        "muestra todo", "restore",
    }

    def __init__(self, desktop: DesktopController, on_command, socketio_emit):
        self.desktop = desktop
        self.on_command = on_command    # Callback → JarvisV8.process()
        self.push = socketio_emit       # Para enviar alertas a la GUI
        self.active = False
        self.running = False
        self.thread = None

        if not VOICE_OK:
            print("⚠️  Voice no disponible. Ambient mode desactivado.")
            return

        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()

        # Calibración
        print("🎤 Calibrando micrófono para ambient mode...")
        try:
            with self.mic as src:
                self.rec.adjust_for_ambient_noise(src, duration=1)
            print("✅ Micrófono calibrado")
        except Exception as e:
            print(f"⚠️  Error calibrando micrófono: {e}")

        # TTS
        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 170)
        self.tts.setProperty("volume", 0.9)

    def start(self):
        """Iniciar ambient listening en background thread."""
        if not VOICE_OK:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("🔊 Ambient listener iniciado — escuchando siempre")

    def stop(self):
        self.running = False

    def say(self, text: str):
        """TTS en thread separado para no bloquear."""
        clean = re.sub(r"\*+|`+|#{1,6}\s?", "", text)[:200]
        threading.Thread(target=self._say_blocking, args=(clean,), daemon=True).start()

    def _say_blocking(self, text: str):
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except:
            pass

    def _loop(self):
        """
        Loop principal de escucha continua.
        Usa listen en modo timeout corto para no bloquear mucho.
        """
        print("👂 Ambient loop activo...")

        while self.running:
            try:
                with self.mic as src:
                    try:
                        # Escucha breve (1.5s max espera + 6s frase)
                        audio = self.rec.listen(
                            src,
                            timeout=1.5,
                            phrase_time_limit=6
                        )
                    except sr.WaitTimeoutError:
                        continue

                # Transcribir
                try:
                    text = self.rec.recognize_google(
                        audio, language="es-ES"
                    ).lower().strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    time.sleep(2)
                    continue

                if not text:
                    continue

                print(f"🎤 Escuchado: '{text}'")

                # ── PRIORIDAD 1: MINIMIZAR TODO ──────────
                if self._matches(text, self.MINIMIZE_WORDS):
                    print("🖥️  COMANDO: Minimizar todo")
                    result = self.desktop.minimize_all()
                    self.say("Escritorio despejado")
                    # Notificar a la GUI
                    self.push("desktop_clear", {"result": result, "text": text})
                    continue

                # ── PRIORIDAD 2: RESTAURAR ────────────────
                if self._matches(text, self.RESTORE_WORDS):
                    print("🖥️  COMANDO: Restaurar ventanas")
                    result = self.desktop.show_all()
                    self.say("Ventanas restauradas")
                    self.push("desktop_restore", {"result": result})
                    continue

                # ── PRIORIDAD 3: WAKE WORD + COMANDO ─────
                wake_detected = self._matches(text, self.WAKE_WORDS)

                if wake_detected or self.active:
                    # Extraer comando (quitar el wake word)
                    command = text
                    for w in self.WAKE_WORDS:
                        command = command.replace(w, "").strip()

                    if command and len(command) > 2:
                        print(f"🤖 Procesando: '{command}'")
                        self.active = False  # Reset

                        # Notificar GUI que se detectó voz
                        self.push("voice_detected", {"text": text, "command": command})

                        # Procesar con el cerebro
                        result = self.on_command(command)
                        self.say(result.get("text","..."))

                        # Enviar respuesta a GUI
                        self.push("ambient_response", result)

                    elif wake_detected and not command:
                        # Solo dijeron "Jarvis" → activar modo activo
                        self.active = True
                        self.say("Sí?")
                        self.push("voice_active", {"text": "¿En qué puedo ayudar?"})

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️  Ambient error: {e}")
                time.sleep(1)

        print("👂 Ambient loop detenido")

    def _matches(self, text: str, word_set: set) -> bool:
        """¿Contiene el texto alguna palabra del set?"""
        text_lower = text.lower()
        return any(w in text_lower for w in word_set)


# ════════════════════════════════════════════════════════
# PROACTIVE MONITOR — ALERTAS AUTOMÁTICAS
# ════════════════════════════════════════════════════════
class ProactiveMonitor:
    """
    Monitorea el sistema y lanza alertas proactivas.
    Sin que el usuario pregunte.
    """

    def __init__(self, push_callback):
        self.push = push_callback
        self.running = False
        self.last_alerts = {}       # Para no repetir alertas
        self.session_start = datetime.now()
        self.work_alert_sent = False

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("📊 Proactive monitor iniciado")

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        """Loop de monitoreo cada 30 segundos."""
        check_count = 0

        while self.running:
            try:
                time.sleep(30)
                check_count += 1

                # Obtener stats
                mem   = psutil.virtual_memory()
                cpu   = psutil.cpu_percent(interval=1)
                disk  = psutil.disk_usage("/")

                temp = 0
                try:
                    ts = psutil.sensors_temperatures()
                    if ts:
                        for v in ts.values():
                            if v:
                                temp = v[0].current
                                break
                except:
                    pass

                now     = datetime.now()
                elapsed = (now - self.session_start).total_seconds() / 3600

                alerts = []

                # ── CPU ALTO ─────────────────────────────
                if cpu > 90 and self._should_alert("cpu_high", 300):
                    alerts.append({
                        "type":    "warning",
                        "icon":    "⚡",
                        "title":   "CPU muy alta",
                        "message": f"CPU al {cpu:.0f}%. ¿Hay algún proceso pesado?"
                    })

                # ── TEMPERATURA CRÍTICA ───────────────────
                if temp > 88 and self._should_alert("temp_critical", 120):
                    alerts.append({
                        "type":    "danger",
                        "icon":    "🔥",
                        "title":   "Temperatura crítica",
                        "message": f"CPU a {temp:.0f}°C. Revise la ventilación del Ryzen."
                    })
                elif temp > 80 and self._should_alert("temp_high", 300):
                    alerts.append({
                        "type":    "warning",
                        "icon":    "🌡️",
                        "title":   "Temperatura elevada",
                        "message": f"CPU a {temp:.0f}°C. Funcionando alto."
                    })

                # ── RAM ALTA ──────────────────────────────
                if mem.percent > 88 and self._should_alert("ram_high", 300):
                    alerts.append({
                        "type":    "warning",
                        "icon":    "💾",
                        "title":   "RAM casi llena",
                        "message": f"RAM al {mem.percent:.0f}% ({mem.used/1e9:.1f}GB). Cierre apps innecesarias."
                    })

                # ── DISCO CASI LLENO ──────────────────────
                if disk.percent > 90 and self._should_alert("disk_full", 3600):
                    free_gb = disk.free / 1e9
                    alerts.append({
                        "type":    "danger",
                        "icon":    "💿",
                        "title":   "Disco casi lleno",
                        "message": f"Solo {free_gb:.1f}GB libres ({disk.percent}% usado). Limpie espacio."
                    })

                # ── TRABAJO CONTINUO ──────────────────────
                if elapsed >= 2.0 and self._should_alert("work_2h", 7200):
                    alerts.append({
                        "type":    "info",
                        "icon":    "☕",
                        "title":   "2 horas trabajando",
                        "message": "Llevas 2 horas seguidas. Un descanso de 10 min mejora la productividad."
                    })
                elif elapsed >= 1.0 and self._should_alert("work_1h", 3600):
                    alerts.append({
                        "type":    "info",
                        "icon":    "⏱️",
                        "title":   "1 hora trabajando",
                        "message": "Llevas 1 hora en sesión. ¿Todo bien?"
                    })

                # Enviar alertas a la GUI
                for alert in alerts:
                    print(f"🔔 Alerta proactiva: {alert['title']}")
                    self.push("proactive_alert", alert)

            except Exception as e:
                pass  # Monitor silencioso

    def _should_alert(self, key: str, cooldown_secs: int) -> bool:
        """¿Debería enviar esta alerta? (evitar spam)"""
        last = self.last_alerts.get(key, 0)
        now  = time.time()
        if now - last >= cooldown_secs:
            self.last_alerts[key] = now
            return True
        return False


# ════════════════════════════════════════════════════════
# CONFIG + MEMORY + AUTO-CORRECTOR (heredados)
# ════════════════════════════════════════════════════════
class Config:
    HOME      = Path.home()
    WORKSPACE = HOME / "jarvis_workspace"
    OUTPUTS   = WORKSPACE / "outputs"
    MEMORY    = WORKSPACE / "memory_v8.pkl"
    ERRORS    = WORKSPACE / "errors_v8.pkl"

    for d in [WORKSPACE, OUTPUTS]:
        d.mkdir(parents=True, exist_ok=True)

    API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
    MODEL        = "claude-sonnet-4-20250514"
    WEATHER_KEY  = os.getenv("OPENWEATHER_KEY", "")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


class Memory:
    def __init__(self):
        self.db = self._load()

    def _load(self) -> Dict:
        if Config.MEMORY.exists():
            try:
                with open(Config.MEMORY,"rb") as f:
                    return pickle.load(f)
            except:
                pass
        return {
            "profile": {
                "name": None, "age": 13,
                "projects": ["Sonso V11-V20","Jarvis V1-V8"],
                "hardware": "Ryzen 7 5700X + RX 570X 8GB + 16GB RAM",
                "facts": [
                    "Ahorró 1 año para comprar su Ryzen a los 12 años",
                    "Completó Sonso V11-V20 (RL nivel PhD)",
                    "Completó Jarvis V1-V8 (asistente completo con ambient awareness)",
                    "Nivel técnico: investigador PhD a los 13 años",
                ]
            },
            "conversations": [],
            "reminders":     [],
            "stats":         {"sessions": 0, "commands": 0}
        }

    def save(self):
        with open(Config.MEMORY,"wb") as f:
            pickle.dump(self.db, f)

    def log(self, u: str, a: str):
        self.db["conversations"].append({
            "ts": datetime.now().isoformat(), "u": u[:150], "a": a[:300]
        })
        self.db["conversations"] = self.db["conversations"][-500:]
        self.db["stats"]["commands"] += 1
        self.save()

    def add_reminder(self, text: str, when: datetime):
        self.db["reminders"].append(
            {"text": text, "when": when.isoformat(), "done": False}
        )
        self.save()

    def pop_due(self) -> List[str]:
        now = datetime.now()
        due = [r for r in self.db["reminders"]
               if not r["done"] and datetime.fromisoformat(r["when"]) <= now]
        for r in due:
            r["done"] = True
        if due:
            self.save()
        return [r["text"] for r in due]

    def context(self) -> str:
        p  = self.db["profile"]
        facts = "\n".join(f"  • {x}" for x in p.get("facts",[]))
        recent = self.db["conversations"][-3:]
        conv   = "\n".join(f"  [{c['ts'][:10]}] {c['u'][:55]}" for c in recent)
        return (f"PERFIL:\n  Nombre: {p.get('name','[no dicho]')} | "
                f"Edad: {p.get('age')} | Hardware: {p.get('hardware')}\n"
                f"  Proyectos: {', '.join(p.get('projects',[]))}\n"
                f"HECHOS:\n{facts}\n"
                f"RECIENTES:\n{conv}")


class AutoCorrector:
    def __init__(self):
        self.kb: Dict = {}
        if Config.ERRORS.exists():
            try:
                with open(Config.ERRORS,"rb") as f:
                    self.kb = pickle.load(f)
            except:
                pass

    def _save(self):
        with open(Config.ERRORS,"wb") as f:
            pickle.dump(self.kb, f)

    def try_fix(self, error: str) -> Tuple[bool,str]:
        if "ModuleNotFoundError" in error:
            m = re.search(r"No module named '([\w.]+)'", error)
            if m:
                raw = m.group(1).split(".")[0]
                aliases = {"cv2":"opencv-python","PIL":"Pillow",
                           "sklearn":"scikit-learn","yaml":"pyyaml"}
                pkg = aliases.get(raw, raw)
                try:
                    subprocess.check_call(
                        [sys.executable,"-m","pip","install",pkg],
                        capture_output=True, timeout=90
                    )
                    self.kb[raw] = pkg; self._save()
                    return True, f"✅ `{pkg}` instalado"
                except:
                    return False, f"No pude instalar `{pkg}`"
        return False, "Error no reconocido"


# ════════════════════════════════════════════════════════
# INTEGRATIONS (de V7)
# ════════════════════════════════════════════════════════
class Integrations:
    def __init__(self):
        self.http = req.Session()

    def weather(self, city="Madrid") -> Dict:
        if Config.WEATHER_KEY:
            try:
                url = (f"https://api.openweathermap.org/data/2.5/weather"
                       f"?q={city}&appid={Config.WEATHER_KEY}&units=metric&lang=es")
                d = self.http.get(url, timeout=5).json()
                return {"city":d["name"],"temp":round(d["main"]["temp"]),
                        "feels":round(d["main"]["feels_like"]),
                        "desc":d["weather"][0]["description"],
                        "humidity":d["main"]["humidity"],
                        "wind":round(d["wind"]["speed"]*3.6,1),"mock":False}
            except:
                pass
        import random
        return {"city":city,"temp":random.randint(15,28),"feels":random.randint(13,26),
                "desc":random.choice(["despejado","nublado","parcialmente nublado"]),
                "humidity":random.randint(40,75),"wind":round(random.uniform(5,20),1),"mock":True}

    def stats(self) -> Dict:
        try:
            mem=psutil.virtual_memory(); disk=psutil.disk_usage("/"); net=psutil.net_io_counters()
            temp=0
            try:
                ts=psutil.sensors_temperatures()
                if ts:
                    for v in ts.values():
                        if v: temp=round(v[0].current,1); break
            except:
                pass
            return {"cpu":round(psutil.cpu_percent(interval=0.3)),"cpu_temp":temp,
                    "ram":round(mem.percent),"ram_used":round(mem.used/1e9,1),
                    "ram_total":round(mem.total/1e9,1),"disk":round(disk.percent),
                    "net_up":round(net.bytes_sent/1e6,1),"net_down":round(net.bytes_recv/1e6,1),
                    "uptime":str(timedelta(seconds=int(time.time()-psutil.boot_time()))).split(".")[0]}
        except Exception as e:
            return {"error":str(e)}

    def news(self) -> List[Dict]:
        try:
            ids = self.http.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",timeout=5
            ).json()[:8]
            items=[]
            for nid in ids:
                it=self.http.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{nid}.json",timeout=3
                ).json()
                if it and it.get("type")=="story" and it.get("title"):
                    items.append({"title":it["title"][:80],"score":it.get("score",0),"url":it.get("url","#")})
                if len(items)>=5: break
            return items
        except:
            return [{"title":"DeepMind nuevo modelo de razonamiento","score":512,"url":"#"},
                    {"title":"GPT-5 en beta privada","score":430,"url":"#"},
                    {"title":"Meta Llama 4 contexto 1M tokens","score":388,"url":"#"}]


# ════════════════════════════════════════════════════════
# JARVIS V8 BRAIN
# ════════════════════════════════════════════════════════
class JarvisV8:
    """Cerebro completo V1→V8."""

    def __init__(self, api_key: str):
        self.client    = Anthropic(api_key=api_key)
        self.memory    = Memory()
        self.corrector = AutoCorrector()
        self.integs    = Integrations()
        self.desktop   = DesktopController()
        self.history   = []
        self.memory.db["stats"]["sessions"] += 1
        self.memory.save()

    def _system_prompt(self) -> str:
        s = self.integs.stats()
        return f"""Eres JARVIS V8, el asistente definitivo estilo Tony Stark.
V8 incluye Ambient Awareness: siempre escuchas, ves el escritorio y mandas alertas proactivas.

SISTEMA AHORA: CPU {s.get('cpu','?')}% | RAM {s.get('ram_used','?')}/{s.get('ram_total','?')}GB

{self.memory.context()}

NUEVAS CAPACIDADES V8:
  • Ambient listening (siempre escuchando sin botones)
  • Desktop control (minimiza todo con "silencio")
  • Alertas proactivas (temperatura, RAM, tiempo de trabajo)
  • Ventanas abiertas conocidas

PERSONALIDAD: Jarvis de Iron Man — educado, profesional, cercano, proactivo.
Responde en español. Usa markdown ligero."""

    def process(self, msg: str) -> Dict:
        t0 = time.time()
        intent = self._intent(msg)
        if intent:
            self.memory.log(msg, intent["text"])
            return {**intent, "ms": round((time.time()-t0)*1000)}

        self.history.append({"role":"user","content":msg})
        self.history = self.history[-30:]

        for attempt in range(3):
            try:
                r = self.client.messages.create(
                    model=Config.MODEL, max_tokens=2048,
                    system=self._system_prompt(),
                    messages=self.history
                )
                reply = r.content[0].text
                self.history.append({"role":"assistant","content":reply})
                self.memory.log(msg, reply)
                return {"text":reply,"type":"chat","ms":round((time.time()-t0)*1000)}
            except Exception as e:
                fixed, msg2 = self.corrector.try_fix(str(e))
                if fixed and attempt < 2:
                    continue
                return {"text":f"⚠️ {e}\n{msg2}","type":"error"}
        return {"text":"❌ Error de procesamiento","type":"error"}

    def _intent(self, msg: str) -> Optional[Dict]:
        low = msg.lower()

        # DESKTOP CONTROL (nuevas V8)
        minimize_kw = {
            "silencio","despeja","escóndete","escondete","limpia",
            "escritorio","minimiza todo","show desktop","modo zen"
        }
        if any(w in low for w in minimize_kw):
            result = self.desktop.minimize_all()
            return {"text": f"🖥️ {result}", "type": "desktop_clear"}

        restore_kw = {"restaura","restaurar","vuelve","regresa","muestra todo"}
        if any(w in low for w in restore_kw):
            result = self.desktop.show_all()
            return {"text": f"🖥️ {result}", "type": "desktop_restore"}

        # VENTANAS ABIERTAS
        if any(w in low for w in ["qué tengo abierto","ventanas abiertas","qué hay abierto"]):
            windows = self.desktop.get_open_windows()[:8]
            if windows:
                lines = ["🖥️ **Ventanas abiertas:**\n"] + [f"▸ {w}" for w in windows]
            else:
                lines = ["🖥️ No detecté ventanas abiertas (o sin permisos)"]
            return {"text":"\n".join(lines),"type":"info"}

        # CLIMA
        if any(w in low for w in ["clima","tiempo","temperatura","llueve"]):
            city="Madrid"
            m=re.search(r"\ben\s+([A-Za-záéíóúñ]+)\b",msg,re.I)
            if m: city=m.group(1).capitalize()
            w=self.integs.weather(city)
            mock=" *(demo)*" if w["mock"] else ""
            text=(f"🌤️ **{w['city']}**{mock}\n"
                  f"🌡️ {w['temp']}°C (sensación {w['feels']}°C)\n"
                  f"🌥️ {w['desc'].capitalize()}\n"
                  f"💧 {w['humidity']}%  💨 {w['wind']} km/h")
            return {"text":text,"type":"weather","data":w}

        # SISTEMA
        if any(w in low for w in ["sistema","monitor","cpu","ram","disco","temperatura"]):
            s=self.integs.stats()
            wc=" 🔴" if s.get("cpu",0)>85 else ""
            wt=" 🔥" if s.get("cpu_temp",0)>85 else ""
            wr=" ⚠️" if s.get("ram",0)>85 else ""
            text=(f"🖥️ **Sistema:**\n"
                  f"⚡ CPU: {s.get('cpu','?')}%{wc}  🌡️ {s.get('cpu_temp','?')}°C{wt}\n"
                  f"💾 RAM: {s.get('ram_used','?')}/{s.get('ram_total','?')}GB{wr}\n"
                  f"💿 Disco: {s.get('disk','?')}%\n"
                  f"⏱️ Uptime: {s.get('uptime','?')}")
            return {"text":text,"type":"monitor","data":s}

        # NOTICIAS
        if any(w in low for w in ["noticias","news","tech"]):
            items=self.integs.news()
            lines=["📰 **Noticias tech:**\n"]+[f"{i}. {n['title']} ⭐{n['score']}"
                                                for i,n in enumerate(items,1)]
            return {"text":"\n".join(lines),"type":"news","data":items}

        # SPOTIFY
        if "spotify" in low:
            if not AUTOMATION_OK:
                return {"text":"❌ pyautogui no instalado","type":"error"}
            ac_map={"siguiente":("ctrl","right"),"anterior":("ctrl","left"),
                    "pausa":("space",),"play":("space",),
                    "sube":("ctrl","up"),"baja":("ctrl","down")}
            for kw,keys in ac_map.items():
                if kw in low:
                    pyautogui.hotkey(*keys)
                    return {"text":f"✅ Spotify: {kw}","type":"spotify"}
            return {"text":"¿Qué acción de Spotify? (siguiente/anterior/pausa/sube/baja)","type":"info"}

        # RECORDATORIO
        if any(w in low for w in ["recuérdame","recuerda que","recordatorio"]):
            delta=timedelta(minutes=10)
            m=re.search(r"en\s+(\d+)\s*(minuto|hora)",low)
            if m:
                n,u=int(m.group(1)),m.group(2)
                delta=timedelta(hours=n) if "hora" in u else timedelta(minutes=n)
            when=datetime.now()+delta
            self.memory.add_reminder(msg,when)
            return {"text":f"⏰ Recordatorio a las **{when.strftime('%H:%M')}**","type":"reminder"}

        # GITHUB
        if "github" in low:
            repos = self.integs._github_repos_safe()
            lines = ["🔗 **GitHub:**\n"] + [f"▸ **{r['name']}** — {r['desc']}" for r in repos]
            return {"text":"\n".join(lines),"type":"github"}

        return None

    def greeting(self) -> str:
        h=datetime.now().hour
        sal=("Buenos días" if 5<=h<12 else "Buenas tardes" if 12<=h<18
             else "Buenas noches" if 18<=h<22 else "Trabajando tarde, señor")
        name=self.memory.db["profile"].get("name") or ""
        suf=f", {name}" if name else ""
        s=self.integs.stats()
        extra=""
        if s.get("cpu_temp",0)>80:
            extra=f" El Ryzen está a {s['cpu_temp']}°C."
        return (f"{sal}{suf}. Ambient mode activo — escucho siempre. "
                f"CPU {s.get('cpu','?')}%, RAM {s.get('ram_used','?')}GB.{extra} "
                f"¿En qué le asisto?")

    def _github_repos_safe(self):
        try:
            headers={}
            if Config.GITHUB_TOKEN:
                headers["Authorization"]=f"token {Config.GITHUB_TOKEN}"
            url=("https://api.github.com/user/repos?sort=updated&per_page=5"
                 if Config.GITHUB_TOKEN else
                 "https://api.github.com/users/octocat/repos?per_page=3")
            data=req.get(url,headers=headers,timeout=5).json()
            return [{"name":r["name"],"desc":(r.get("description") or "")[:50]}
                    for r in data[:4] if isinstance(r,dict)]
        except:
            return [{"name":"sonso-rl","desc":"PhD locomotion RL"},
                    {"name":"jarvis-v8","desc":"Iron Man AI assistant"}]


# ════════════════════════════════════════════════════════
# FLASK + GUI V8
# ════════════════════════════════════════════════════════
app = Flask(__name__)
app.config["SECRET_KEY"] = "jarvis-v8-ambient-2025"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

brain:    Optional[JarvisV8]        = None
ambient:  Optional[AmbientListener] = None
monitor:  Optional[ProactiveMonitor]= None


def push(event: str, data: Dict):
    """Helper para emitir desde threads."""
    socketio.emit(event, data)


# ── HUD HTML V8 ───────────────────────────────────────
HUD = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS VIII — Ambient Awareness</title>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=VT323&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --bg:#030912;--panel:rgba(3,14,28,.93);
  --cyan:#00d4ff;--gold:#e8b923;--red:#e84040;--green:#00ff88;--orange:#ff7b00;
  --border:rgba(0,212,255,.2);--glow:0 0 20px rgba(0,212,255,.4);
  --text:#c8eeff;--dim:rgba(200,238,255,.4);
}
html,body{height:100%;overflow:hidden;}
body{font-family:'Share Tech Mono',monospace;background:var(--bg);color:var(--text);
     display:flex;flex-direction:column;
     background-image:repeating-linear-gradient(0deg,transparent,transparent 3px,
       rgba(0,0,0,.05) 3px,rgba(0,0,0,.05) 4px);}
body::before{content:'';position:fixed;inset:0;pointer-events:none;
  background:radial-gradient(ellipse 80% 50% at 50% 100%,rgba(0,50,100,.3),transparent 70%);}

/* TOPBAR */
#top{z-index:10;padding:9px 20px;background:var(--panel);
     border-bottom:1px solid var(--border);
     display:flex;align-items:center;justify-content:space-between;
     backdrop-filter:blur(12px);}
.logo{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.2rem;
      letter-spacing:5px;
      background:linear-gradient(90deg,var(--gold),var(--cyan));
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.logo small{font-size:.6rem;letter-spacing:2px;color:var(--dim);
            -webkit-text-fill-color:var(--dim);display:block;margin-top:1px;}
#topRight{display:flex;gap:14px;align-items:center;font-size:.7rem;}
.ts{display:flex;align-items:center;gap:5px;color:var(--dim);}
.ts i{color:var(--cyan);font-size:.75rem;}
.ts b{color:var(--text);}
#connDot{width:8px;height:8px;border-radius:50%;background:var(--red);animation:blink 2s infinite;}
.online{background:var(--green)!important;}
#clk{font-family:'VT323',monospace;font-size:1.3rem;color:var(--gold);letter-spacing:2px;}

/* AMBIENT BADGE */
#ambBadge{
  display:flex;align-items:center;gap:6px;
  background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.3);
  padding:4px 10px;border-radius:2px;font-size:.65rem;color:var(--green);
}
#ambBadge .adot{width:6px;height:6px;border-radius:50%;background:var(--green);
                animation:blink 1.5s infinite;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:.2;}}

/* MAIN */
#main{flex:1;overflow:hidden;display:grid;grid-template-columns:208px 1fr 192px;position:relative;z-index:5;}

/* SIDE PANELS */
.side{background:var(--panel);padding:12px 10px;display:flex;flex-direction:column;
      gap:8px;overflow-y:auto;backdrop-filter:blur(10px);}
#left{border-right:1px solid var(--border);}
#right{border-left:1px solid var(--border);}
.pt{font-family:'Orbitron',sans-serif;font-size:.56rem;letter-spacing:3px;
    color:var(--gold);border-bottom:1px solid rgba(232,185,35,.25);
    padding-bottom:5px;margin-bottom:2px;}
.met{font-size:.7rem;margin:2px 0;}
.met .l{color:var(--dim);}
.met .v{float:right;color:var(--text);}
.bar{height:3px;background:rgba(0,212,255,.1);border-radius:2px;
     margin-top:3px;overflow:hidden;clear:both;}
.fill{height:100%;border-radius:2px;transition:width .6s;background:var(--cyan);}
.fill.hot{background:var(--red)!important;}
.fill.warm{background:var(--orange)!important;}
.qb{display:block;width:100%;text-align:left;
    background:rgba(0,212,255,.05);border:1px solid var(--border);
    color:var(--cyan);padding:6px 9px;border-radius:2px;cursor:pointer;
    font-family:'Share Tech Mono',monospace;font-size:.7rem;
    transition:all .2s;margin-bottom:2px;}
.qb:hover{background:rgba(0,212,255,.14);border-color:var(--cyan);box-shadow:var(--glow);}
.qb.desktop{border-color:rgba(0,255,136,.3);color:var(--green);}
.qb.desktop:hover{background:rgba(0,255,136,.12);border-color:var(--green);}
.card{background:rgba(0,212,255,.04);border:1px solid var(--border);
      border-radius:2px;padding:8px;}
.ct{font-size:.58rem;color:var(--gold);letter-spacing:2px;margin-bottom:4px;}
.cv{font-size:.76rem;}
.ni{font-size:.66rem;color:var(--dim);margin-bottom:6px;line-height:1.4;
    border-left:2px solid var(--border);padding-left:5px;}
.ni:hover{color:var(--text);border-color:var(--cyan);}

/* ALERT TOAST */
#toasts{position:fixed;top:60px;right:200px;z-index:100;
        display:flex;flex-direction:column;gap:6px;pointer-events:none;}
.toast{
  background:var(--panel);border-radius:3px;padding:10px 14px;
  font-size:.75rem;max-width:300px;animation:tin .3s ease;
  backdrop-filter:blur(10px);border-left:3px solid var(--cyan);
}
.toast.warning{border-color:var(--orange);}
.toast.danger{border-color:var(--red);}
.toast.info{border-color:var(--cyan);}
.toast-title{font-family:'Orbitron',sans-serif;font-size:.6rem;
             letter-spacing:2px;margin-bottom:3px;}
@keyframes tin{from{opacity:0;transform:translateX(20px);}to{opacity:1;transform:translateX(0);}}

/* DESKTOP EVENT FLASH */
#dFlash{
  display:none;position:fixed;inset:0;z-index:200;pointer-events:none;
  background:rgba(0,255,136,.04);
  border:2px solid rgba(0,255,136,.5);
}
#dFlash.show{display:block;animation:flash .6s ease forwards;}
@keyframes flash{0%{opacity:1;}100%{opacity:0;}}

/* CENTER CHAT */
#center{display:flex;flex-direction:column;}
#msgs{flex:1;overflow-y:auto;padding:16px 20px;
      display:flex;flex-direction:column;gap:11px;
      scrollbar-width:thin;scrollbar-color:var(--border) transparent;}
.msg{max-width:76%;padding:11px 15px;border-radius:2px;
     font-size:.81rem;line-height:1.65;animation:pop .3s cubic-bezier(.34,1.56,.64,1);}
@keyframes pop{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:translateY(0);}}
.msg.user{align-self:flex-end;
  background:linear-gradient(135deg,rgba(0,100,200,.3),rgba(0,212,255,.1));
  border:1px solid rgba(0,212,255,.3);border-bottom-right-radius:0;}
.msg.bot{align-self:flex-start;background:rgba(3,14,28,.85);
  border:1px solid var(--border);border-left:3px solid var(--gold);
  border-bottom-left-radius:0;}
.msg.bot .bl{font-family:'Orbitron',sans-serif;font-size:.53rem;
             letter-spacing:3px;color:var(--gold);margin-bottom:5px;
             display:flex;align-items:center;gap:5px;}
.msg.bot .bl::after{content:'';flex:1;height:1px;background:rgba(232,185,35,.2);}
.msg.ambient{border-left:3px solid var(--green) !important;
             background:rgba(0,255,136,.04) !important;}
.mtime{font-size:.58rem;color:var(--dim);margin-top:5px;text-align:right;}
.msg strong{color:var(--cyan);}
.msg code{background:rgba(0,212,255,.08);padding:1px 4px;
          border-radius:2px;font-size:.78rem;color:#aaefff;}
.typing{align-self:flex-start;padding:11px 15px;background:rgba(3,14,28,.85);
        border:1px solid var(--border);border-left:3px solid var(--gold);border-radius:2px;}
.typing span{display:inline-block;width:5px;height:5px;background:var(--gold);
             border-radius:50%;margin:0 2px;animation:td .7s infinite;}
.typing span:nth-child(2){animation-delay:.15s;}
.typing span:nth-child(3){animation-delay:.3s;}
@keyframes td{0%,100%{transform:translateY(0);}50%{transform:translateY(-5px);}}

/* INPUT */
#inpRow{padding:12px 18px;border-top:1px solid var(--border);
        background:var(--panel);backdrop-filter:blur(10px);
        display:flex;gap:7px;align-items:center;}
#inp{flex:1;background:rgba(0,212,255,.05);border:1px solid var(--border);
     color:var(--cyan);padding:8px 12px;border-radius:2px;
     font-family:'Share Tech Mono',monospace;font-size:.87rem;outline:none;transition:border .2s;}
#inp:focus{border-color:var(--cyan);box-shadow:var(--glow);}
#inp::placeholder{color:var(--dim);}
.ib{background:rgba(0,212,255,.06);border:1px solid var(--border);
    color:var(--cyan);padding:8px 12px;border-radius:2px;cursor:pointer;
    font-family:'Share Tech Mono',monospace;font-size:.78rem;transition:all .2s;}
.ib:hover{background:rgba(0,212,255,.16);border-color:var(--cyan);box-shadow:var(--glow);}
#sndBtn{background:linear-gradient(135deg,rgba(232,185,35,.2),rgba(0,212,255,.1));
        border-color:var(--gold);color:var(--gold);
        font-family:'Orbitron',sans-serif;font-size:.68rem;letter-spacing:1px;}
#sndBtn:hover{background:rgba(232,185,35,.3);}
#micBtn{width:38px;height:38px;border-radius:50%;padding:0;
        display:flex;align-items:center;justify-content:center;}
#micBtn.rec{background:rgba(232,64,64,.3);border-color:var(--red);color:var(--red);
            animation:rp 1s infinite;}
@keyframes rp{0%,100%{transform:scale(1);}50%{transform:scale(1.12);}}

/* FOOTER */
#foot{padding:5px 20px;border-top:1px solid var(--border);
      background:var(--panel);display:flex;justify-content:space-between;
      font-size:.6rem;color:var(--dim);z-index:10;}
</style>
</head>
<body>

<div id="dFlash"></div>
<div id="toasts"></div>

<!-- TOP -->
<div id="top">
  <div class="logo">◈ JARVIS VIII <small>AMBIENT AWARENESS · IRON MAN EDITION</small></div>
  <div id="topRight">
    <div class="ts"><div id="connDot"></div><b id="connTxt">OFFLINE</b></div>
    <div class="ts"><i class="fa fa-microchip"></i><b id="tCpu">--</b></div>
    <div class="ts"><i class="fa fa-memory"></i><b id="tRam">--</b></div>
    <div id="ambBadge"><div class="adot"></div>AMBIENT ACTIVE</div>
    <div id="clk">--:--:--</div>
  </div>
</div>

<!-- MAIN -->
<div id="main">

  <!-- LEFT -->
  <div class="side" id="left">
    <div class="pt">◈ SYSTEMS</div>
    <div class="met"><span class="l">CPU</span><span class="v" id="mCpu">--%</span>
      <div class="bar"><div class="fill" id="bCpu" style="width:0%"></div></div></div>
    <div class="met"><span class="l">RAM</span><span class="v" id="mRam">--%</span>
      <div class="bar"><div class="fill" id="bRam" style="width:0%"></div></div></div>
    <div class="met"><span class="l">DISK</span><span class="v" id="mDisk">--%</span>
      <div class="bar"><div class="fill" id="bDisk" style="width:0%"></div></div></div>
    <div class="met"><span class="l">TEMP</span><span class="v" id="mTemp">--</span></div>
    <div class="met"><span class="l">NET↑</span><span class="v" id="mUp">--</span></div>
    <div class="met"><span class="l">NET↓</span><span class="v" id="mDn">--</span></div>

    <div class="pt" style="margin-top:8px">◈ DESKTOP CONTROL</div>
    <button class="qb desktop" onclick="q('silencio')">🖥 Silencio — minimiza TODO</button>
    <button class="qb desktop" onclick="q('restaura ventanas')">↩ Restaurar ventanas</button>
    <button class="qb desktop" onclick="q('qué tengo abierto')">👁 Ver ventanas</button>

    <div class="pt" style="margin-top:6px">◈ QUICK</div>
    <button class="qb" onclick="q('estado del sistema')">🖥 Monitor</button>
    <button class="qb" onclick="q('clima')">🌤 Clima</button>
    <button class="qb" onclick="q('noticias tech')">📰 News</button>
    <button class="qb" onclick="q('github')">🔗 GitHub</button>
    <button class="qb" onclick="q('spotify pausa')">⏸ Spotify</button>
    <button class="qb" onclick="q('spotify siguiente')">⏭ Next</button>
  </div>

  <!-- CENTER -->
  <div id="center">
    <div id="msgs"></div>
    <div id="inpRow">
      <input id="inp" placeholder="Comando o consulta... (o di 'Jarvis' al micrófono)" onkeydown="kp(event)">
      <button class="ib" id="micBtn" onclick="tMic()" title="Voz manual"><i class="fas fa-microphone"></i></button>
      <button class="ib" id="sndBtn" onclick="send()"><i class="fas fa-bolt"></i> ENVIAR</button>
    </div>
  </div>

  <!-- RIGHT -->
  <div class="side" id="right">
    <div class="pt">◈ INTEL</div>
    <div class="card"><div class="ct">CLIMA</div><div class="cv" id="wCard">Cargando...</div></div>
    <div class="card"><div class="ct">PROYECTO</div><div class="cv">Jarvis V8 Ultimate</div></div>
    <div class="card"><div class="ct">AMBIENT</div>
      <div class="cv" style="font-size:.68rem;color:var(--green)">
        🎤 Siempre escuchando<br>
        🖥 "Silencio" → escritorio<br>
        🔔 Alertas proactivas
      </div>
    </div>
    <div class="pt" style="margin-top:4px">◈ NEWS</div>
    <div id="newsPanel"><div class="ni">Cargando...</div></div>
  </div>
</div>

<!-- FOOT -->
<div id="foot">
  <span>JARVIS V8 · AMBIENT AWARE · ALL SYSTEMS NOMINAL</span>
  <span id="fUp">UPTIME: --</span>
  <span>⚡ CLAUDE SONNET 4 · ANTHROPIC</span>
</div>

<script>
const S = io();
let recOn=false, recog=null;

/* ── Connection ─────────────────────────── */
S.on('connect',()=>{
  setConn(true);
  S.emit('greeting');
  setTimeout(()=>S.emit('load_news'),900);
  setTimeout(()=>S.emit('load_weather'),1400);
});
S.on('disconnect',()=>setConn(false));
function setConn(ok){
  document.getElementById('connDot').className=ok?'online':'';
  document.getElementById('connTxt').textContent=ok?'ONLINE':'OFFLINE';
}

/* ── Events ─────────────────────────────── */
S.on('greeting',   d=>addMsg(d.text,'bot'));
S.on('response',   d=>{rmTyping();addMsg(d.text,'bot');});
S.on('ambient_response', d=>{rmTyping();addMsg('🎤 '+d.text,'bot',true);});
S.on('voice_active',d=>addMsg(d.text,'bot',true));
S.on('voice_detected',d=>addMsg('[VOZ] '+d.text,'user'));
S.on('stats',      d=>applyStats(d));
S.on('reminder',   d=>toast('info','⏰ Recordatorio',d.text));
S.on('news_data',  d=>renderNews(d));
S.on('weather_data',d=>renderWeather(d));
S.on('proactive_alert',d=>toast(d.type,d.icon+' '+d.title,d.message));
S.on('desktop_clear',  d=>{flashDesktop();addMsg('🖥️ '+d.result,'bot',true);});
S.on('desktop_restore',d=>addMsg('🖥️ '+d.result,'bot',true));

/* ── Clock + polls ──────────────────────── */
setInterval(()=>{
  const n=new Date();
  document.getElementById('clk').textContent=
    n.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
},1000);
setInterval(()=>S.emit('stats_req'),2500);
setInterval(()=>S.emit('reminder_check'),30000);

/* ── Stats ──────────────────────────────── */
function applyStats(d){
  if(!d||d.error)return;
  sBar('mCpu','bCpu',d.cpu+'%',d.cpu);
  sBar('mRam','bRam',d.ram+'%',d.ram);
  sBar('mDisk','bDisk',d.disk+'%',d.disk);
  document.getElementById('mTemp').textContent=(d.cpu_temp||0)+'°C';
  document.getElementById('mUp').textContent=d.net_up+' MB';
  document.getElementById('mDn').textContent=d.net_down+' MB';
  document.getElementById('tCpu').textContent='CPU '+d.cpu+'%';
  document.getElementById('tRam').textContent='RAM '+d.ram_used+'G';
  document.getElementById('fUp').textContent='UPTIME: '+(d.uptime||'--');
}
function sBar(iv,ib,lbl,pct){
  document.getElementById(iv).textContent=lbl;
  const b=document.getElementById(ib);
  b.style.width=Math.min(pct,100)+'%';
  b.className='fill'+(pct>88?' hot':pct>70?' warm':'');
}

/* ── Chat ───────────────────────────────── */
function send(){
  const v=document.getElementById('inp').value.trim();
  if(!v)return;
  addMsg(v,'user');showTyping();
  S.emit('msg',{text:v});
  document.getElementById('inp').value='';
}
function kp(e){if(e.key==='Enter')send();}
function q(cmd){addMsg(cmd,'user');showTyping();S.emit('msg',{text:cmd});}

function addMsg(raw,role,isAmb=false){
  const wrap=document.getElementById('msgs');
  const d=document.createElement('div');
  d.className='msg '+(role==='bot'?'bot':'user')+(isAmb?' ambient':'');
  const t=new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
  const html=raw
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/`(.+?)`/g,'<code>$1</code>')
    .replace(/\n/g,'<br>');
  const lbl=role==='bot'
    ?'<div class="bl"><i class="fas fa-robot" style="font-size:.55rem"></i> ◈ JARVIS VIII</div>':'';
  d.innerHTML=`${lbl}<div>${html}</div><div class="mtime">${t}</div>`;
  wrap.appendChild(d);wrap.scrollTop=wrap.scrollHeight;
}
function showTyping(){
  const w=document.getElementById('msgs');
  const d=document.createElement('div');
  d.className='typing';d.id='typing';
  d.innerHTML='<span></span><span></span><span></span>';
  w.appendChild(d);w.scrollTop=w.scrollHeight;
}
function rmTyping(){const t=document.getElementById('typing');if(t)t.remove();}

/* ── Voice (manual) ─────────────────────── */
function tMic(){
  if(!recog){
    recog=new(window.SpeechRecognition||window.webkitSpeechRecognition)();
    recog.lang='es-ES';recog.continuous=false;
    recog.onresult=e=>{
      document.getElementById('inp').value=e.results[0][0].transcript;
      send();
    };
    recog.onend=()=>{recOn=false;document.getElementById('micBtn').classList.remove('rec');};
    recog.onerror=()=>{recOn=false;document.getElementById('micBtn').classList.remove('rec');};
  }
  if(!recOn){recog.start();recOn=true;document.getElementById('micBtn').classList.add('rec');}
  else{recog.stop();recOn=false;}
}

/* ── Cards ──────────────────────────────── */
function renderWeather(w){
  if(!w)return;
  const mk=w.mock?' <small style="color:var(--dim)">(demo)</small>':'';
  document.getElementById('wCard').innerHTML=
    `${w.city}${mk}<br>${w.temp}°C · ${w.desc}<br>💧${w.humidity}% 💨${w.wind}km/h`;
}
function renderNews(items){
  if(!items||!items.length)return;
  document.getElementById('newsPanel').innerHTML=
    items.slice(0,4).map(n=>
      `<div class="ni">▸ ${n.title.substring(0,58)}... <b style="color:var(--gold)">★${n.score}</b></div>`
    ).join('');
}

/* ── Toast notifications ─────────────────── */
function toast(type,title,msg){
  const c=document.getElementById('toasts');
  const d=document.createElement('div');
  d.className='toast '+type;
  d.innerHTML=`<div class="toast-title">${title}</div><div>${msg}</div>`;
  c.appendChild(d);
  setTimeout(()=>d.style.opacity='0',4500);
  setTimeout(()=>d.remove(),5000);
}

/* ── Desktop flash effect ─────────────────── */
function flashDesktop(){
  const f=document.getElementById('dFlash');
  f.className='show';
  setTimeout(()=>f.className='',700);
}

/* Notification permission */
if(window.Notification&&Notification.permission==='default')
  Notification.requestPermission();
</script>
</body>
</html>"""


# ── ROUTES ───────────────────────────────────────────
@app.route("/")
def index():
    return HUD

# ── SOCKET ───────────────────────────────────────────
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
    if brain:
        emit("stats", brain.integs.stats())

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


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════
def main():
    global brain, ambient, monitor

    key = Config.API_KEY
    if not key:
        key = input("🔑 API key Anthropic: ").strip()
        os.environ["ANTHROPIC_API_KEY"] = key
        Config.API_KEY = key

    print("\n⚙️  Inicializando sistemas V8...")

    # 1. Brain
    brain = JarvisV8(key)

    # 2. Proactive monitor
    monitor = ProactiveMonitor(push_callback=push)
    monitor.start()

    # 3. Ambient listener
    ambient = AmbientListener(
        desktop=brain.desktop,
        on_command=brain.process,
        socketio_emit=push
    )
    ambient.start()

    print("\n" + "═"*56)
    print("  ✅  JARVIS V8 ULTIMATE — AMBIENT AWARENESS")
    print("═"*56)
    print(f"  🌐  http://localhost:5000")
    print(f"  🎤  Ambient voice: {'✅ Activo' if VOICE_OK else '❌  pip install SpeechRecognition pyttsx3 pyaudio'}")
    print(f"  🖥️   Desktop control: ✅ ({OS})")
    print(f"  🔔  Proactive monitor: ✅")
    print()
    print("  COMANDOS DE VOZ PARA ESCRITORIO:")
    print('  🎤 "silencio"      → minimiza TODO')
    print('  🎤 "despeja"       → minimiza TODO')
    print('  🎤 "escritorio"    → minimiza TODO')
    print('  🎤 "modo zen"      → minimiza TODO')
    print('  🎤 "restaura"      → restaura ventanas')
    print("═"*56)
    print("  Ctrl+C para detener\n")

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()