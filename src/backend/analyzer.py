"""
================================================================================
SMART CV FILTER - AI ANALYZER ENGINE (GOOGLE GEMINI)
================================================================================
Author: Tebagl
Date: April 2026
Version: 2.0 (Cloud Migration)

Description:
Core analysis module that interfaces with Google Gemini through the 
OpenAI-compatible endpoint of Google AI Studio. This engine processes raw CV 
text against job descriptions using gemini-3.1-flash-lite to provide objective 
scoring and justification.

TECHNICAL SPECIFICATIONS:
- Provider: Google AI Studio (Gemini API, OpenAI-compatible endpoint)
- Model: gemini-3.1-flash-lite
- Response Format: Strict JSON (score, apto, motivo)
- Temperature: 0.0 (Deterministic output for consistency)

SECURITY & PRIVACY:
- API keys are loaded via environment variables (conf.env) to prevent leaks.
- No local LLM overhead: Offloads processing to remote inference.
- Data handled via encrypted HTTPS requests.

DATA FLOW:
1. Load API Key -> 2. Construct Prompt -> 3. POST Request -> 4. JSON Parse
================================================================================
"""

import requests
import json
import os
import time
from dotenv import load_dotenv
from pathlib import Path

class CVAnalyzer:
    def __init__(self):
        # 1. Intentar cargar el conf.env con ruta absoluta dentro del init
        # Localización robusta: subimos dos niveles desde src/backend a la raíz
        script_dir = Path(__file__).resolve().parent
        dotenv_path = script_dir.parent.parent / 'conf.env'
        
        load_dotenv(dotenv_path=dotenv_path)
        
        raw_key = os.getenv("GEMINI_API_KEY")
        self.api_key = raw_key.strip() if raw_key else None
        
        self.url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        self.model = "gemini-3.1-flash-lite"
        
        
        # 3. Inicializar headers
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        # Motivo del último fallo de analyze(): "rate_limit", "timeout", "server_busy", "format", "connection", "api" o None
        self.last_error = None

        # Función opcional (ej. la cola de log de la GUI) que recibe los avisos de reintento
        self.status_callback = None

        self.system_prompt = (
            "Eres un reclutador experto que responde solo en JSON. "
            "IMPORTANTE: Devuelve ÚNICAMENTE el objeto JSON válido. Asegúrate de cerrar correctamente las cadenas "
            "con comillas dobles antes de la llave de cierre (ejemplo: {\"score\": 80, \"apto\": \"SI\", "
            "\"motivo\": \"texto explicativo sin comillas internas\"}). No añadas llaves dobles al final."
        )

        # 3. DEFINICIÓN DE LA PLANTILLA
        self.prompt_template = """
        Misión: Actúa como un reclutador profesional para evaluar la idoneidad del candidato para el puesto: {job_description}.
        
        ANÁLISIS DE COHERENCIA PROFESIONAL:
        1. PESO DE LA TRAYECTORIA: Valora el historial completo del candidato. Una experiencia sólida de más de 10 años en las competencias requeridas por el puesto es un activo de alto valor.
        
        2. FACTOR DE DESCONEXIÓN ACTUAL: Analiza si el candidato está actualmente en un proceso de cambio de carrera (estudiando o trabajando en algo totalmente ajeno a la vacante).
           - REGLA: Si el candidato tiene gran experiencia pasada en el sector de la vacante, pero su presente indica una reorientación activa hacia otra industria, resta entre 15 y 20 puntos al score.
           - MOTIVO: Estos perfiles son "Transicionales". Tienen el conocimiento, pero su interés profesional actual está en otro lugar. Deben ser validados manualmente.

        3. AJUSTE DE NIVEL:
           - Para puestos de entrada (Junior/Ayudante): Prioriza formación reciente y actitud.
           - Para puestos especialistas: Prioriza experiencia técnica demostrable.

        ESCALAS DE PUNTUACIÓN:
        - 85-100: PERFIL ACTIVO. Coincidencia total entre su situación actual, su formación y el puesto.
        - 60-84: PERFIL TRANSICIONAL O CON LAGUNAS (DUDAS). Posee las capacidades técnicas por su pasado, pero su situación actual genera dudas sobre su permanencia o foco.
        - 0-59: PERFIL NO ALINEADO. Falta de competencias base o trayectoria totalmente ajena.

        Responde en JSON:
        {{
          "score": número,
          "apto": "SI" o "NO",
          "motivo": "Explica la relación entre la trayectoria pasada del candidato y su situación profesional presente respecto a la vacante."
        }}

        TEXTO DEL CV (ANONIMIZADO):
        {cv_text}
        """


    def set_api_key(self, api_key):
        """Actualiza la clave y los headers para las peticiones."""
        if api_key:
            self.api_key = api_key.strip()
            # Esta línea es la que permite que la conexión funcione tras meterla en el popup
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            print("✅ Analyzer: API Key actualizada correctamente.")
            return True # Indicamos que todo salió bien
        else:
            print("❌ Error: Se intentó configurar una API Key vacía o inválida.")
            return False # Indicamos que hubo un fallo


    def _notify(self, message):
        print(message)
        if self.status_callback:
            self.status_callback(message)

    def _repair_failed_generation(self, raw):
        """Intenta recuperar un JSON válido de la generación rechazada por Gemini."""
        if not raw or not isinstance(raw, str):
            return None

        text = raw.strip()
        start = text.find('{')
        if start == -1:
            return None
        text = text[start:]

        candidates = [text, text[:text.rfind('}') + 1]]
        # Caso típico: la cadena de "motivo" queda sin cerrar y termina en '}}'
        body = text.rstrip().rstrip('}').rstrip()
        candidates.append(body + '}')
        if not body.endswith('"'):
            candidates.append(body + '"}')

        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict) and "score" in data:
                return json.dumps(data, ensure_ascii=False)
        return None

    def analyze(self, cv_text, job_description):
        self.last_error = None
        # Usamos self.prompt_template que definimos en el __init__
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.prompt_template.format(cv_text=cv_text, job_description=job_description)}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "max_tokens": 4096
        }

        max_retries = 5
        # Esperas cuando el 429 no trae Retry-After: una por cada reintento (max_retries - 1)
        backoff_waits = [10, 20, 35, 50]
        timeout_wait = 5
        last_failure = None

        for attempt in range(max_retries):
            try:
                # (conexión, lectura): el modelo puede tardar en generar la respuesta
                response = requests.post(self.url, headers=self.headers, json=payload, timeout=(10, 60))
            except requests.exceptions.Timeout:
                last_failure = "timeout"
                if attempt == max_retries - 1:
                    break
                self._notify(f"⏳ Tiempo de espera agotado (timeout). Reintentando (intento {attempt + 1}/{max_retries})...")
                time.sleep(timeout_wait)
                continue
            except Exception as e:
                # Si hay error de conexión o timeout, devolvemos string vacío
                print(f"❌ Error de conexión: {e}")
                self.last_error = "connection"
                return ""

            if response.status_code == 200:
                # Retornamos el contenido si la respuesta es exitosa
                return response.json()['choices'][0]['message']['content']

            if response.status_code == 429 or response.status_code in (500, 502, 503, 504):
                last_failure = "rate_limit" if response.status_code == 429 else "server_busy"
                if attempt == max_retries - 1:
                    break

                if response.status_code == 429:
                    try:
                        wait_time = float(response.headers.get("Retry-After"))
                    except (TypeError, ValueError):
                        wait_time = backoff_waits[attempt]
                    self._notify(
                        f"⏳ Límite de cuota alcanzado (429). Esperando {wait_time:g}s antes de reintentar (intento {attempt + 1}/{max_retries})..."
                    )
                else:
                    wait_time = backoff_waits[attempt]
                    self._notify(
                        f"⏳ Servidor de Gemini saturado ({response.status_code}). Esperando {wait_time:g}s para reintentar (intento {attempt + 1}/{max_retries})..."
                    )
                time.sleep(wait_time)
                continue

            if response.status_code == 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                # La API compatible de Google puede devolver el error dentro de una lista
                if isinstance(body, list):
                    body = body[0] if body else {}
                error_info = body.get("error", {}) if isinstance(body, dict) else {}

                if error_info.get("code") == "json_validate_failed":
                    repaired = self._repair_failed_generation(error_info.get("failed_generation"))
                    if repaired:
                        print("🔧 JSON inválido de Gemini (400) reparado a partir de 'failed_generation'.")
                        return repaired
                    print(f"❌ JSON inválido de Gemini (400) no reparable: {error_info.get('failed_generation')}")
                    self.last_error = "format"
                    return ""

            # Otros errores de API (ej. 401, 400): devolvemos string vacío para evitar el NoneType
            print(f"❌ Error API Gemini: {response.status_code} - {response.text}")
            self.last_error = "api"
            return ""

        if last_failure == "timeout":
            self._notify(f"❌ Tiempo de espera agotado tras {max_retries} intentos. El CV queda pendiente en la carpeta de entrada.")
        elif last_failure == "server_busy":
            self._notify(f"❌ Servidor de Gemini saturado tras {max_retries} intentos. El CV queda pendiente en la carpeta de entrada.")
        else:
            self._notify(f"❌ Límite de cuota de Gemini persistente tras {max_retries} intentos. El CV queda pendiente en la carpeta de entrada.")
        self.last_error = last_failure
        return ""