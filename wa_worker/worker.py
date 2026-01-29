import asyncio
import json
import sys
import os
from whatsplay import Client
from whatsplay.auth import LocalProfileAuth

# Configuración de path para importar el core (Mantenemos tu estructura)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.redis_client import r
from core.routing import router

async def main():
    # 1. Configuración inicial
    auth = LocalProfileAuth("./sessions")
    client = Client(auth=auth, headless=False)
    
    navegador_lock = asyncio.Lock()
    
    processed_messages = {}
    
    def get_message_hash(chat_name, message_text, sender_name):
        """Genera un hash único para cada mensaje"""
        import hashlib
        content = f"{chat_name}:{sender_name}:{message_text}"
        return hashlib.md5(content.encode()).hexdigest()

    # 2. Tarea en segundo plano para leer mensajes que vienen de Discord
    async def redis_listener():
        print("👂 [WSP Worker] Escuchando Redis (queue_ds_to_wa)...")
        while True:
            try:
                resultado = await r.brpop("queue_ds_to_wa", timeout=1)
                
                if resultado:
                    _, mensaje_json = resultado
                    data = json.loads(mensaje_json)
                    
                    target = data.get('destino_wa')
                    texto = data.get('texto')
                    autor = data.get('autor')

                    if target and texto:
                        async with navegador_lock:
                            print(f"📤 Enviando a {target}: {texto}")
                            await client.send_message(
                                chat_query=target,
                                message=f"**[DS - {autor}]:** {texto}"
                            )
            except Exception as e:
                print(f"❌ Error en loop Redis WSP: {e}")
                await asyncio.sleep(5)
            
            await asyncio.sleep(0.1)

    # 3. Evento: Mensajes entrantes de WhatsApp -> Discord
    @client.event("on_unread_chat")
    @client.event("on_unread_chat")
    async def process_unread_chats(chats): return
        
        print(f"📬 {len(chats)} chat(s) sin leer detectado(s)")
        
        async with navegador_lock:
            for chat_info in chats:
                try:
                    chat_name = chat_info.get('name') or chat_info.get('title')
                    
                    if not chat_name:
                        print(f"⚠️ No se pudo obtener nombre del chat: {chat_info}")
                        continue
                    
                    print(f"📩 Procesando: {chat_name}")
                    
                    # Abrir chat y leer mensajes
                    success = await client.open(chat_name)
                    if not success:
                        print(f"❌ No se pudo abrir {chat_name}")
                        continue
                    
                    messages = await client.collect_messages()
                    
                    if not messages:
                        print(f"⚠️ No hay mensajes en {chat_name}")
                        continue
                    
                    # Procesar solo el último mensaje
                    message = messages[-1]
                    
                    # sender puede ser un string o un objeto
                    if hasattr(message.sender, 'name'):
                        sender_name = message.sender.name
                    else:
                        sender_name = str(message.sender) or chat_name
                    
                    message_text = message.text or ""
                    
                    if not message_text:
                        print(f"⚠️ Mensaje vacío de {chat_name}")
                        continue
                    
                    # Generar hash del mensaje
                    msg_hash = get_message_hash(chat_name, message_text, sender_name)
                    
                    # Inicializar si es el primer mensaje de este chat
                    if chat_name not in processed_messages:
                        processed_messages[chat_name] = set()
                    
                    # Verificar si ya fue procesado
                    if msg_hash in processed_messages[chat_name]:
                        print(f"⏭️ {chat_name}: Mensaje duplicado, ignorando")
                        continue
                    
                    # Marcar como procesado
                    processed_messages[chat_name].add(msg_hash)
                    
                    # Resolvemos a qué canal de Discord va
                    destino_ds = await router.resolve(chat_name)
                    
                    if destino_ds:
                        payload = {
                            "autor": sender_name,
                            "texto": message_text,
                            "destino_ds": destino_ds,
                            "origen": "whatsapp"
                        }
                        
                        await r.lpush("queue_wa_to_ds", json.dumps(payload))
                        print(f"✅ [{chat_name}] → Discord: {message_text[:50]}...")
                    else:
                        print(f"⚠️ [{chat_name}] Sin mapeo en router")
                
                except Exception as e:
                    print(f"❌ Error procesando {chat_info}: {e}")

    @client.event("on_qr")
    async def on_qr(qr):
        print("📲 Escanea el código QR para iniciar sesión.")

    # 4. Arranque
    print("🚀 Iniciando Worker de WhatsApp...")
    
    # Inicializar router
    await router.initialize()
    
    # Esto corre la función en paralelo sin bloquear el inicio del cliente
    asyncio.create_task(redis_listener())
    
    # start() suele ser bloqueante en estas librerías, por eso va al final
    await client.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Apagando...")