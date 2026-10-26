import os
from pathlib import Path
from dotenv import load_dotenv
import requests

base_path = Path(__file__).resolve().parents[1]
env_path = base_path / 'conf.env'
load_dotenv(dotenv_path=env_path)

api_key = os.getenv('GEMINI_API_KEY')

if not api_key:
    print('❌ ERROR: No se lee la clave del conf.env')
    print(f'Buscando en: {env_path}')
else:
    print(f'✅ Clave detectada (empieza por: {api_key[:6]}...)')
    url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {'model': 'gemini-3.1-flash-lite', 'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 5}
    try:
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            print('🚀 CONEXIÓN EXITOSA CON GEMINI')
        else:
            print(f'⚠️ Error de API: {res.status_code} - {res.text}')
    except Exception as e:
        print(f'🔥 Error de red: {e}')
