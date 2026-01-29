import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from core.routing import router

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.redis_client import r
from core.routing import router

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def escuchar_respuestas_whatsapp():
    """
    Tarea en background: Espera mensajes de la cola 'queue_wa_to_ds'
    """
    await bot.wait_until_ready()
    print("🎧 [Discord] Escuchando cola de WhatsApp...")

    while not bot.is_closed():
        try:
            # BRPOP: Se congela acá hasta que WA meta un mensaje
            resultado = await r.brpop("queue_wa_to_ds", timeout=1)
            
            if resultado:
                _, mensaje_json = resultado
                data = json.loads(mensaje_json)
                destino_id = data.get('destino_ds')
                
                if destino_id:
                    canal = bot.get_channel(int(destino_id))
                    if canal:
                        await canal.send(f"**[WA - {data['autor']}]:** {data['texto']}")
                        print(f"[Discord] Publicado en el canal: {data['texto']}")
                    else:
                        print(f"[Error] Canal {destino_id} no encontrado")

        except Exception as e:
            print(f"Error leyendo Redis: {e}")
            await asyncio.sleep(2)

@bot.event
async def on_ready():
    print(f'Bot online como {bot.user}')
    await router.initialize()
    bot.loop.create_task(escuchar_respuestas_whatsapp())

@bot.event
async def on_message(message):
    if message.author.bot: return
    destino_wa = await router.resolve(message.channel.id)
    if destino_wa:
        payload = {
            "autor": message.author.display_name,
            "texto": message.clean_content,
            "destino_wa": destino_wa
        }
        
        await r.lpush("queue_ds_to_wa", json.dumps(payload))
        print(f"[Discord] Enviado a Redis: {payload['texto']}")

if __name__ == "__main__":
    bot.run(TOKEN)