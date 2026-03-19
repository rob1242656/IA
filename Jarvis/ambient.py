"""
JARVIS V8 — Ambient Module
============================
DesktopController, TTSWorker, AmbientListener, ProactiveMonitor.
Thread-safe, recursos gestionados, sin leaks.
"""

import os, re, time, threading, subprocess, platform, queue
from datetime import datetime
from typing import Dict, List, Callable, Optional

import psutil

from brain import (
    MINIMIZE_KEYWORDS, RESTORE_KEYWORDS, WAKE_WORDS,
    StatsCache
)

# Opcional: voice
VOICE_OK = False
try:
    import speech_recognition as sr
    import pyttsx3
    VOICE_OK = True
except ImportError:
    pass

# Opcional: pyautogui
AUTOMATION_OK = False
try:
    import pyautogui
    AUTOMATION_OK = True
except ImportError:
    pass

OS = platform.system()


# ════════════════════════════════════════════════════════
# DESKTOP CONTROLLER
# ════════════════════════════════════════════════════════
class DesktopController:
    """
    Controla el escritorio a nivel de OS.
    Windows, Linux y Mac con cadena de fallbacks.
    """

    def __init__(self):
        self.os = platform.system()
        self._check_dependencies()

    def _check_dependencies(self):
        if self.os == "Windows":
            try:
                import win32gui, win32con  # noqa: F401
                self.win32_ok = True
            except ImportError:
                self.win32_ok = False
                print("⚠️  pywin32 no disponible — pip install pywin32")
        elif self.os == "Linux":
            self.xdotool = subprocess.run(
                ["which", "xdotool"], capture_output=True
            ).returncode == 0
            self.wmctrl = subprocess.run(
                ["which", "wmctrl"], capture_output=True
            ).returncode == 0
        elif self.os == "Darwin":
            self.applescript_ok = True

    def minimize_all(self) -> str:
        """Minimizar TODAS las ventanas."""
        if self.os == "Windows":
            return self._minimize_windows()
        elif self.os == "Linux":
            return self._minimize_linux()
        elif self.os == "Darwin":
            return self._minimize_mac()
        return "Sistema operativo no soportado"

    def _minimize_windows(self) -> str:
        # Metodo 1: Win32 API
        try:
            import win32gui, win32con
            def minimize_window(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            win32gui.EnumWindows(minimize_window, None)
            return "✅ Escritorio despejado (Win32 API)"
        except Exception:
            pass
        # Metodo 2: Win+D
        if AUTOMATION_OK:
            try:
                pyautogui.hotkey("win", "d")
                time.sleep(0.3)
                return "✅ Escritorio mostrado (Win+D)"
            except Exception:
                pass
        # Metodo 3: PowerShell
        try:
            script = '(New-Object -ComObject Shell.Application).MinimizeAll()'
            subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, timeout=5
            )
            return "✅ Escritorio despejado (PowerShell)"
        except Exception:
            pass
        return "No se pudo minimizar — instala pywin32"

    def _minimize_linux(self) -> str:
        if getattr(self, 'xdotool', False):
            try:
                subprocess.run(
                    ["xdotool", "key", "super+d"],
                    capture_output=True, timeout=3
                )
                return "✅ Escritorio mostrado (xdotool Super+D)"
            except Exception:
                pass
            try:
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
            except Exception:
                pass
        if getattr(self, 'wmctrl', False):
            try:
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
            except Exception:
                pass
        if AUTOMATION_OK:
            try:
                pyautogui.hotkey("super", "d")
                return "✅ Escritorio mostrado (Super+D)"
            except Exception:
                pass
        return "⚠️ Instala xdotool: sudo apt-get install xdotool"

    def _minimize_mac(self) -> str:
        script = 'tell application "System Events" to set visible of every process to false'
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return "✅ Escritorio mostrado (AppleScript)"
        except Exception:
            pass
        if AUTOMATION_OK:
            try:
                pyautogui.hotkey("command", "mission_control")
                return "✅ Mission Control activado"
            except Exception:
                pass
        return "⚠️ Activa permisos de Accessibility en Preferencias del Sistema"

    def show_all(self) -> str:
        """Restaurar todas las ventanas minimizadas."""
        if self.os == "Windows":
            if AUTOMATION_OK:
                try:
                    pyautogui.hotkey("win", "shift", "m")
                    return "✅ Ventanas restauradas"
                except Exception:
                    pass
            try:
                script = '(New-Object -ComObject Shell.Application).UndoMinimizeAll()'
                subprocess.run(
                    ["powershell", "-Command", script],
                    capture_output=True, timeout=5
                )
                return "✅ Ventanas restauradas (PowerShell)"
            except Exception:
                return "No se pudo restaurar"
        elif self.os == "Linux":
            if getattr(self, 'wmctrl', False):
                try:
                    result = subprocess.run(
                        ["wmctrl", "-l"], capture_output=True, text=True
                    )
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            wid = line.split()[0]
                            subprocess.run(
                                ["wmctrl", "-i", "-r", wid, "-b", "remove,hidden"],
                                capture_output=True
                            )
                    return "✅ Ventanas restauradas"
                except Exception:
                    pass
        elif self.os == "Darwin":
            try:
                subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to set visible of every process to true'],
                    capture_output=True, timeout=5
                )
                return "✅ Ventanas restauradas"
            except Exception:
                pass
        return "No se pudo restaurar"

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
            except Exception:
                pass
        elif self.os == "Linux":
            if getattr(self, 'wmctrl', False):
                try:
                    r = subprocess.run(
                        ["wmctrl", "-l"], capture_output=True, text=True
                    )
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append(parts[3])
                except Exception:
                    pass
        elif self.os == "Darwin":
            try:
                script = ('tell application "System Events" to '
                          'get name of every window of every process')
                r = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=5
                )
                windows = r.stdout.strip().split(", ")
            except Exception:
                pass
        return [w for w in windows if w and len(w) > 1]


# ════════════════════════════════════════════════════════
# TTS WORKER — Thread-safe voice output
# ════════════════════════════════════════════════════════
class TTSWorker:
    """
    Motor de voz en un thread dedicado.
    pyttsx3 usa COM en Windows (thread-affine), por eso
    TODAS las llamadas al engine se hacen desde UN solo thread.
    Seguro llamar say() desde cualquier thread.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Loop principal — crea engine EN este thread."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 0.9)
        except Exception as e:
            print(f"⚠️ TTS init error: {e}")
            return

        while self._running:
            try:
                text = self._queue.get(timeout=1.0)
                if text is None:  # Poison pill → shutdown
                    break
                engine.say(text)
                engine.runAndWait()
            except queue.Empty:
                continue
            except Exception:
                pass

    def say(self, text: str):
        """Thread-safe. Encola texto para hablar."""
        clean = re.sub(r"\*+|`+|#{1,6}\s?", "", str(text))[:200]
        if clean.strip():
            self._queue.put(clean)

    def shutdown(self):
        """Detiene el worker limpiamente."""
        self._running = False
        self._queue.put(None)  # Poison pill


# ════════════════════════════════════════════════════════
# AMBIENT LISTENER — Siempre escuchando
# ════════════════════════════════════════════════════════
class AmbientListener:
    """
    Escucha el microfono en background.
    Detecta wake words y comandos especiales.
    """

    def __init__(self, desktop: DesktopController, tts: Optional[TTSWorker],
                 on_command: Callable, push: Callable):
        self.desktop = desktop
        self.tts = tts
        self.on_command = on_command
        self.push = push
        self._active = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        if not VOICE_OK:
            print("⚠️ Voice no disponible. Ambient mode desactivado.")
            print("   Instala: pip install SpeechRecognition pyttsx3 pyaudio")
            return

        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()

        # Calibracion
        print("🎤 Calibrando microfono para ambient mode...")
        try:
            with self.mic as src:
                self.rec.adjust_for_ambient_noise(src, duration=1)
            print("✅ Microfono calibrado")
        except Exception as e:
            print(f"⚠️ Error calibrando microfono: {e}")

    def start(self):
        if not VOICE_OK:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("🔊 Ambient listener iniciado — escuchando siempre")

    def stop(self):
        self._running = False

    def _say(self, text: str):
        """Habla via TTS worker (thread-safe)."""
        if self.tts:
            self.tts.say(text)

    def _loop(self):
        """Loop principal. Mantiene mic abierto, re-abre solo en error."""
        print("👂 Ambient loop activo...")
        while self._running:
            try:
                with self.mic as src:
                    while self._running:
                        try:
                            audio = self.rec.listen(
                                src, timeout=1.5, phrase_time_limit=6
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
                        self._handle_speech(text)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Ambient error: {e}")
                time.sleep(2)  # Back-off antes de re-abrir mic

        print("👂 Ambient loop detenido")

    def _handle_speech(self, text: str):
        """Procesa texto reconocido."""
        # PRIORIDAD 1: MINIMIZAR TODO
        if self._matches(text, MINIMIZE_KEYWORDS):
            print("🖥️ COMANDO: Minimizar todo")
            result = self.desktop.minimize_all()
            self._say("Escritorio despejado")
            self.push("desktop_clear", {"result": result, "text": text})
            return

        # PRIORIDAD 2: RESTAURAR
        if self._matches(text, RESTORE_KEYWORDS):
            print("🖥️ COMANDO: Restaurar ventanas")
            result = self.desktop.show_all()
            self._say("Ventanas restauradas")
            self.push("desktop_restore", {"result": result})
            return

        # PRIORIDAD 3: WAKE WORD + COMANDO
        wake_detected = self._matches(text, WAKE_WORDS)

        if wake_detected or self._active.is_set():
            # Extraer comando (quitar el wake word)
            command = text
            for w in WAKE_WORDS:
                command = command.replace(w, "").strip()

            if command and len(command) > 2:
                print(f"🤖 Procesando: '{command}'")
                self._active.clear()
                self.push("voice_detected", {"text": text, "command": command})
                result = self.on_command(command)
                self._say(result.get("text", "..."))
                self.push("ambient_response", result)

            elif wake_detected and not command:
                # Solo dijeron "Jarvis" → activar modo activo
                self._active.set()
                self._say("Si?")
                self.push("voice_active", {"text": "¿En que puedo ayudar?"})

    @staticmethod
    def _matches(text: str, word_set: frozenset) -> bool:
        return any(w in text for w in word_set)


# ════════════════════════════════════════════════════════
# PROACTIVE MONITOR — Alertas automaticas
# ════════════════════════════════════════════════════════
class ProactiveMonitor:
    """
    Monitorea el sistema y lanza alertas proactivas.
    Lee stats del StatsCache (zero-blocking).
    """

    def __init__(self, stats_cache: StatsCache, push_callback: Callable):
        self.push = push_callback
        self._stats_cache = stats_cache
        self._running = False
        self._last_alerts: Dict[str, float] = {}
        self._session_start = datetime.now()

    def start(self):
        self._running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("📊 Proactive monitor iniciado")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        """Loop de monitoreo cada 30 segundos. Lee del cache, NO bloquea."""
        while self._running:
            time.sleep(30)
            try:
                s = self._stats_cache.get()
                if not s:
                    continue

                cpu = s.get("cpu", 0)
                temp = s.get("cpu_temp", 0)
                ram_pct = s.get("ram", 0)
                disk_pct = s.get("disk", 0)
                elapsed = (datetime.now() - self._session_start).total_seconds() / 3600

                alerts = []

                # CPU ALTO
                if cpu > 90 and self._should_alert("cpu_high", 300):
                    alerts.append({
                        "type": "warning", "icon": "⚡",
                        "title": "CPU muy alta",
                        "message": f"CPU al {cpu}%. ¿Hay algun proceso pesado?"
                    })

                # TEMPERATURA CRITICA
                if temp > 88 and self._should_alert("temp_critical", 120):
                    alerts.append({
                        "type": "danger", "icon": "🔥",
                        "title": "Temperatura critica",
                        "message": f"CPU a {temp}°C. Revise la ventilacion del Ryzen."
                    })
                elif temp > 80 and self._should_alert("temp_high", 300):
                    alerts.append({
                        "type": "warning", "icon": "🌡️",
                        "title": "Temperatura elevada",
                        "message": f"CPU a {temp}°C. Funcionando alto."
                    })

                # RAM ALTA
                if ram_pct > 88 and self._should_alert("ram_high", 300):
                    ram_used = s.get("ram_used", "?")
                    alerts.append({
                        "type": "warning", "icon": "💾",
                        "title": "RAM casi llena",
                        "message": f"RAM al {ram_pct}% ({ram_used}GB). Cierre apps innecesarias."
                    })

                # DISCO CASI LLENO
                if disk_pct > 90 and self._should_alert("disk_full", 3600):
                    alerts.append({
                        "type": "danger", "icon": "💿",
                        "title": "Disco casi lleno",
                        "message": f"Disco al {disk_pct}%. Limpie espacio."
                    })

                # TRABAJO CONTINUO
                if elapsed >= 2.0 and self._should_alert("work_2h", 7200):
                    alerts.append({
                        "type": "info", "icon": "☕",
                        "title": "2 horas trabajando",
                        "message": "Un descanso de 10 min mejora la productividad."
                    })
                elif elapsed >= 1.0 and self._should_alert("work_1h", 3600):
                    alerts.append({
                        "type": "info", "icon": "⏱️",
                        "title": "1 hora trabajando",
                        "message": "Llevas 1 hora en sesion. ¿Todo bien?"
                    })

                for alert in alerts:
                    print(f"🔔 Alerta: {alert['title']}")
                    self.push("proactive_alert", alert)

            except Exception:
                pass

    def _should_alert(self, key: str, cooldown_secs: int) -> bool:
        """Evitar spam de alertas."""
        last = self._last_alerts.get(key, 0)
        now = time.time()
        if now - last >= cooldown_secs:
            self._last_alerts[key] = now
            return True
        return False
