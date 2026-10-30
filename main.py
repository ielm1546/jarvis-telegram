import os
import re
import time
import asyncio
import threading
import requests
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import RPCError

# --- CONFIGURACIÓN DE TELEGRAM (USERBOT) ---
API_ID = 33606964
API_HASH = "756fd02aae2deb1ee44148ebf390d293"
SESSION_STRING = os.environ.get("SESSION_STRING")
ADMIN_CHAT_ID = 6235877284            # Tu ID numérico privado para alertas
CANAL_ID = "@comics2035"              # Canal oficial de destino

# Expresión regular para detectar enlaces HTTP/HTTPS
URL_REGEX = r'https?://[^\s]+'

# Cliente de Telethon usando la StringSession de la nube
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def verificar_enlace(url):
    """Comprueba si un enlace está activo. Detecta códigos HTTP y pantallas de error genéricas."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        respuesta = requests.get(url, headers=headers, timeout=7, allow_redirects=True)
        
        if respuesta.status_code >= 400:
            return False
            
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
    """Recorre TODOS los mensajes, limpia excesos de tachos acumulados y verifica estados."""
    print("🤖 Jarvis (UserBot): Iniciando escaneo y limpieza en el canal...", flush=True)
    
    contador_revisados = 0
    async for message in client.iter_messages(CANAL_ID):
        texto = message.text
        if not texto:
            continue

        enlaces = re.findall(URL_REGEX, texto)
        if not enlaces:
            continue

        hubo_cambio = False
        nuevo_texto = texto

        # 1. FASE DE LIMPIEZA: Normalizar tachos múltiples previos en el mensaje
        for url in enlaces:
            if "t.me/" in url or "telegram.me/" in url:
                continue

            # Limpiamos rastros duplicados o cadenas deformadas de [Caído]
            limpio_de_taches = nuevo_texto.replace(f"~~{url}~~", url)
            limpio_de_etiquetas = limpio_de_taches.replace(" 🔴 [Caído]", "").replace("🔴 [Caído]", "")
            
            if limpio_de_etiquetas != nuevo_texto:
                nuevo_texto = limpio_de_etiquetas
                hubo_cambio = True

        # 2. FASE DE VERIFICACIÓN Y MARCADO ÚNICO
        enlaces_limpios = re.findall(URL_REGEX, nuevo_texto)
        
        for url in enlaces_limpios:
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

                marcador_caido = f"~~{url}~~ 🔴 [Caído]"
                if marcador_caido not in nuevo_texto:
                    nuevo_texto = nuevo_texto.replace(url, marcador_caido)
                    hubo_cambio = True

            await asyncio.sleep(1)

        if hubo_cambio:
            try:
                await client.edit_message(CANAL_ID, message.id, nuevo_texto)
                print(f"✨ Mensaje #{message.id} limpiado y actualizado correctamente.", flush=True)
            except RPCError as e:
                print(f"Error al editar mensaje #{message.id}: {e}", flush=True)

    print(f"✅ Escaneo y limpieza completa finalizados. Total analizados: {contador_revisados}.", flush=True)

async def iniciar_bot_y_bucle():
    if not SESSION_STRING:
        print("❌ Error crítico: La variable de entorno SESSION_STRING no está configurada en Render.", flush=True)
        return

    print("Conectando UserBot con Telegram mediante StringSession...", flush=True)
    await client.start()
    print("¡Conexión exitosa con Telegram!", flush=True)
    
    try:
        await client.send_message(ADMIN_CHAT_ID, "🤖 **Jarvis (UserBot) activo:** Conectado, sistema de limpieza anti-paintball activado e intervalo de 1 hora configurado.")
    except Exception:
        pass

    while True:
        try:
            await revisar_todo_el_canal()
        except Exception as e:
            print(f"Error en la ronda de revisión: {e}", flush=True)

        print("⏳ Esperando 1 hora para el siguiente ciclo de revisión...", flush=True)
        await asyncio.sleep(3600)  # Intervalo de 1 hora (3600 segundos)

def bucle_infinito():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(iniciar_bot_y_bucle())

# --- SERVIDOR WEB PARA RENDER (Evita suspensión 24/7) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Jarvis UserBot activo con autolimpieza de enlaces y ciclo de 1 hora."

if __name__ == "__main__":
    hilo = threading.Thread(target=bucle_infinito)
    hilo.daemon = True
    hilo.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
