import os
import re
import time
import asyncio
import threading
import requests
from flask import Flask
from telethon import TelegramClient
from telethon.errors import RPCError

# --- CONFIGURACIÓN DE TELEGRAM ---
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
# Ahora el token se lee de forma segura desde las variables de entorno de Render
TOKEN_BOT = os.environ.get("TOKEN_BOT")
ADMIN_CHAT_ID = 6235877284                 # Tu ID numérico privado para alertas

CANAL_ID = "@Comic_series"                  # Tu canal de Telegram

# Expresión regular para detectar enlaces HTTP/HTTPS en los mensajes
URL_REGEX = r'https?://[^\s]+'

# Cliente de Telethon con sesión guardada
client = TelegramClient('sesion_jarvis', API_ID, API_HASH)

def verificar_enlace(url):
    """Comprueba si un enlace está activo y responde con código HTTP 200-299."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        respuesta = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        return 200 <= respuesta.status_code < 300
    except requests.RequestException:
        return False

async def revisar_todo_el_canal():
    """Recorre TODOS los mensajes publicados en la historia del canal."""
    print("🤖 Jarvis: Iniciando escaneo completo del historial del canal...")
    
    async for message in client.iter_messages(CANAL_ID):
        texto = message.text or message.caption
        if not texto:
            continue

        enlaces = re.findall(URL_REGEX, texto)
        if not enlaces:
            continue

        hubo_cambio = False
        nuevo_texto = texto

        for url in enlaces:
            if "t.me/" in url or "telegram.me/" in url:
                continue

            print(f"Verificando [Mensaje ID {message.id}]: {url}")

            if not verificar_enlace(url):
                print(f"⚠️ ¡ENLACE CAÍDO DETECTADO en mensaje {message.id}!")
                
                try:
                    await client.send_message(
                        ADMIN_CHAT_ID,
                        f"🚨 **ALERTA JARVIS**\n\nEnlace caído en el mensaje **#{message.id}**:\n`{url}`"
                    )
                except Exception as e:
                    print(f"Error enviando alerta privada: {e}")

                if url in nuevo_texto and not f"~~{url}~~" in nuevo_texto:
                    nuevo_texto = nuevo_texto.replace(url, f"~~{url}~~ ❌ (Caído)")
                    hubo_cambio = True

            await asyncio.sleep(1)

        if hubo_cambio:
            try:
                await client.edit_message(CANAL_ID, message.id, nuevo_texto)
                print(f"✅ Mensaje #{message.id} actualizado con la marca de caído.")
            except RPCError as e:
                print(f"Error al editar mensaje #{message.id}: {e}")

    print("✅ Escaneo completo finalizado.")

def bucle_infinito():
    """Ejecuta el escaneo de todo el canal continuamente cada 6 horas."""
    if not TOKEN_BOT:
        print("❌ Error crítico: La variable de entorno TOKEN_BOT no está configurada en Render.")
        return

    client.start(bot_token=TOKEN_BOT)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            loop.run_until_complete(revisar_todo_el_canal())
        except Exception as e:
            print(f"Error en la ronda de revisión: {e}")

        print("⏳ Esperando 6 horas para volver a escanear todo el canal...")
        time.sleep(21600)

# --- SERVIDOR WEB PARA RENDER (Evita suspensión 24/7) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Jarvis Bot está activo escaneando todo el canal 24/7."

if __name__ == "__main__":
    hilo = threading.Thread(target=bucle_infinito)
    hilo.daemon = True
    hilo.start()

    app.run(host="0.0.0.0", port=10000)
