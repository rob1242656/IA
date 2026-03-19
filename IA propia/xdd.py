import pyautogui
import time
import json
import requests
import re
import easyocr
import cv2
import numpy as np
import pyperclip # Nueva librería para leer lo copiado

# --- CONFIGURACIÓN ---
MODELO = "llama3" 
API_URL = "http://localhost:11434/api/generate"
pyautogui.FAILSAFE = True

print("👁️ Cargando sistema de visión... (Esto tarda un poco)")
lector_ocr = easyocr.Reader(['es', 'en'], gpu=False)
print("✅ Sistemas listos.")

# --- EL CEREBRO: PROMPT DEL SISTEMA (V1.5 - EL INVESTIGADOR) ---
SYSTEM_PROMPT = """
Eres Ozymandias, un Agente Autónomo de Investigación.
Tu misión: Navegar, extraer información y resumirla.

HERRAMIENTAS:
1. "teclas": Atajos (["win"], ["ctrl", "c"], ["ctrl", "a"], ["alt", "tab"]).
2. "escribir": Texto normal.
3. "click_visual": Busca texto en pantalla y haz clic (EJ: "Wikipedia", "Noticias").
4. "esperar": Segundos de pausa.
5. "leer_y_resumir": ¡NUEVO! Úsalo cuando ya hayas copiado texto. Valor = "Nombre del archivo a guardar" (ej: "resumen_cuantica.txt").

ESTRATEGIA DE INVESTIGACIÓN (¡SÍGUELA!):
1. Abre navegador con 'win' y busca el tema.
2. Espera a que cargue.
3. Usa "click_visual" para entrar en un resultado prometedor (ej: buscar palabras clave en pantalla).
4. Selecciona todo ("ctrl", "a") y copia ("ctrl", "c").
5. Ejecuta "leer_y_resumir" para procesar la info.

EJEMPLO: Usuario: "Investiga sobre Sonso Robot"
Tú:
[
    {"accion": "teclas", "valor": ["win"]},
    {"accion": "esperar", "valor": 1.0},
    {"accion": "escribir", "valor": "Sonso Robot Reinforcement Learning"},
    {"accion": "teclas", "valor": ["enter"]},
    {"accion": "esperar", "valor": 3.0},
    {"accion": "click_visual", "valor": "Videos"}, 
    {"accion": "esperar", "valor": 2.0},
    {"accion": "teclas", "valor": ["ctrl", "a"]},
    {"accion": "teclas", "valor": ["ctrl", "c"]},
    {"accion": "esperar", "valor": 0.5},
    {"accion": "leer_y_resumir", "valor": "sonso_info.txt"}
]

RESPONDE SOLO CON EL JSON:
"""

def consultar_llama(prompt, system_p=SYSTEM_PROMPT):
    # Función genérica para hablar con Llama
    payload = {
        "model": MODELO, "prompt": prompt, "system": system_p, 
        "stream": False, "options": {"temperature": 0.1}
    }
    try:
        r = requests.post(API_URL, json=payload)
        txt = r.json().get("response", "")
        # Limpieza JSON
        clean = re.sub(r"```json|```", "", txt).strip()
        if "]" in clean: clean = clean[:clean.rfind("]")+1]
        
        # Si no parece JSON (es resumen de texto), devolver texto
        if not clean.startswith("["): return txt
        return json.loads(clean)
    except:
        return [] if system_p == SYSTEM_PROMPT else "Error generando resumen."

# --- MÓDULO DE INTELIGENCIA (RESUMEN) ---
def generar_resumen(texto_copiado, nombre_archivo):
    print(f"🧠 Leyendo {len(texto_copiado)} caracteres del portapapeles...")
    
    # Recortamos si es muy largo para no saturar a Llama (max 6000 chars)
    texto_input = texto_copiado[:6000]
    
    prompt_resumen = f"""
    El usuario ha copiado el siguiente texto de una web.
    Haz un resumen estructurado, en español, destacando los puntos clave.
    
    TEXTO:
    {texto_input}
    """
    
    print("✍️ Redactando resumen...")
    # Usamos una llamada directa a Llama, pero sin el Prompt de JSON estricto
    resumen = consultar_llama(prompt_resumen, system_p="Eres un asistente útil que resume textos.")
    
    if isinstance(resumen, str):
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(resumen)
        print(f"✅ ¡Resumen guardado en '{nombre_archivo}'!")
        
        # Opcional: Abrir el archivo para mostrarlo
        import os
        os.system(f"start {nombre_archivo}")

# --- EL OJO ---
def buscar_y_clickear(texto_objetivo):
    print(f"👁️ Buscando: '{texto_objetivo}'...")
    sc = pyautogui.screenshot()
    frame = np.array(sc)
    res = lector_ocr.readtext(frame)
    
    for (bbox, txt, conf) in res:
        if texto_objetivo.lower() in txt.lower() and conf > 0.4:
            cx = int((bbox[0][0] + bbox[2][0]) / 2)
            cy = int((bbox[0][1] + bbox[2][1]) / 2)
            pyautogui.moveTo(cx, cy, duration=0.5)
            pyautogui.click()
            return
    print(f"⚠️ No encontré '{texto_objetivo}'.")

# --- EL EJECUTOR ---
def ejecutar_plan(plan):
    if not plan: return
    print(f"🦾 Ejecutando {len(plan)} pasos...")
    
    for paso in plan:
        tipo = paso.get("accion")
        valor = paso.get("valor")
        
        print(f"   -> {tipo}: {valor}")
        
        if tipo == "teclas":
            if isinstance(valor, list): pyautogui.hotkey(*[str(v).lower() for v in valor])
            else: pyautogui.press(str(valor).lower())
        
        elif tipo == "escribir":
            pyautogui.write(str(valor), interval=0.05)
            
        elif tipo == "esperar":
            time.sleep(float(valor))
            
        elif tipo == "click_visual":
            buscar_y_clickear(str(valor))
            
        elif tipo == "leer_y_resumir":
            # Extraer contenido del portapapeles
            contenido = pyperclip.paste()
            generar_resumen(contenido, str(valor))

if __name__ == "__main__":
    print("🤖 Ozymandias V1.5: MODO INVESTIGADOR.")
    
    while True:
        orden = input("\n¿Qué quieres investigar?: ") # Ej: "Investiga sobre Python y guarda resumen"
        if orden.lower() == "salir": break
        
        plan = consultar_llama(orden)
        if isinstance(plan, list):
            print("PLAN:", plan)
            input("⚠️ Presiona ENTER para iniciar la investigación...")
            ejecutar_plan(plan)
        else:
            print("❌ Llama no generó un plan válido.")