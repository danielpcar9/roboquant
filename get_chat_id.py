# get_chat_id.py
import os
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Obtener actualizaciones del bot
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
response = requests.get(url)
data = response.json()

print("Respuesta completa:")
print(data)

if data.get('ok') and data.get('result'):
    for update in data['result']:
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            username = update['message']['chat'].get('username', 'N/A')
            print(f"\nChat ID encontrado: {chat_id}")
            print(f"Username: {username}")
else:
    print("\nNo hay mensajes. Asegurate de:")
    print("1. Buscar tu bot en Telegram")
    print("2. Presionar Start o enviar /start")
    print("3. Ejecutar este script de nuevo")