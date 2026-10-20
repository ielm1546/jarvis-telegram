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
TOKEN_BOT = os.environ.get("TOKEN_BOT")
ADMIN_CHAT_ID = 6235877284            # Tu ID numérico privado para alertas
CANAL_ID = "@Comic_series"              # Tu canal de Telegram

# Expresión regular para detectar enlaces HTTP/HTTPS
URL_REGEX = r'https?://[^\s]+'

# Cliente de Telethon
client = TelegramClient('sesion_jarvis', API_ID, API_HASH)

def verificar_enlace(url):
    """Comprueba si un enlace está activo. Detecta códigos HTTP y pantallas de error 404 genéricas."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # Timeout optimizado a 7 segundos para agilizar la revisión masiva
        respuesta = requests.get(url, headers=headers, timeout=7, allow_redirects=True)
        
        # Si da error HTTP directo (404, 500, etc.)
        if respuesta.status_code >= 400:
            return False
            
        # Analizar el contenido HTML para detectar la pantalla de error genérica del acortador
        cuerpo_html = respuesta.text.lower()
        palabras_error = [
            "404 no encontrado", 
            "no se encontró en este servidor", 
            "link not found", 
            "file deleted", 
            "enlace no encontrado", 
            "archivo borrado", 
            "page not found", 
            "expired", 
            "removed"
        ]
        
        for palabra in palabras_error:
            if palabra in cuerpo_html:
                print(f"-> Detectado enlace caído por texto en la página: {url}", flush=True)
                return False

        return True
    except requests.RequestException as e:
        print(f"Excepción de red al verificar {url}: {e}", flush=True)
        return False

async def revisar_todo_el_canal():
    """Recorre TODOS los mensajes publicados en la historia del canal."""
    print("🤖 Jarvis: Iniciando escaneo completo del historial del canal...", flush=True)
    
    contador_revisados = 0
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

            contador_revisados += 1
            print(f"Verificando [Mensaje ID {message.id}]: {url}", flush=True)

            if not verificar_enlace(url):
                print(f"⚠️ ¡ENLACE CAÍDO DETECTADO en mensaje {message.id}!", flush=True)
                
                try:
                    await client.send_message(
                        ADMIN_CHAT_ID,
                        f"🚨 **ALERTA JARVIS**\n\nEnlace caído en el mensaje **#{message.id}**:\n`{url}`"
                    )
                except Exception as e:
                    print(f"Error enviando alerta privada: {e}", flush=True)

                if url in nuevo_texto and not f"~~{url}~~" in nuevo_texto:
                    # Nuevo formato visual con círculo rojo para el canal
                    nuevo_texto = nuevo_texto.replace(url, f"~~{url}~~ 🔴 [Caído]")
                    hubo_cambio = True

            await asyncio.sleep(1)

        if hubo_cambio:
            try:
                await client.edit_message(CANAL_ID, message.id, nuevo_texto)
                print(f"✅ Mensaje #{message.id} actualizado con la marca de caído.", flush=True)
            except RPCError as e:
                print(f"Error al editar mensaje #{message.id}: {e}", flush=True)

    print(f"✅ Escaneo completo finalizado. Total de enlaces analizados: {contador_revisados}.", flush=True)

async def iniciar_bot_y_bucle():
    if not TOKEN_BOT:
        print("❌ Error crítico: La variable de entorno TOKEN_BOT no está configurada en Render.", flush=True)
        return

    print("Conectando con Telegram...", flush=True)
    await client.start(bot_token=TOKEN_BOT)
    print("¡Conexión exitosa con Telegram!", flush=True)
    
    try:
        await client.send_message(ADMIN_CHAT_ID, "🤖 **Jarvis activo:** El bot se ha conectado y comenzó el monitoreo.")
    except Exception:
        pass

    while True:
        try:
            await revisar_todo_el_canal()
        except Exception as e:
            print(f"Error en la ronda de revisión: {e}", flush=True)

        print("⏳ Esperando 6 horas para volver a escanear todo el canal...", flush=True)
        await asyncio.sleep(21600)

def bucle_infinito():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(iniciar_bot_y_bucle())

# --- SERVIDOR WEB PARA RENDER (Evita suspensión 24/7) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Jarvis Bot está activo escaneando todo el canal 24/7."

if __name__ == "__main__":
    hilo = threading.Thread(target=bucle_infinito)
    hilo.daemon = True
    hilo.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
