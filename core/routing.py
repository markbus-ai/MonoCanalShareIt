import json
import os
import asyncio
import sys
# Importamos la conexión que ya creamos antes
from core.redis_client import r 

class AsyncRouter:
    def __init__(self, config_path="mapping.json"):
        self.config_path = config_path
        # Claves de Redis (Hash Sets)
        self.REDIS_KEY_DS = "bridge:map:ds_to_wa"
        self.REDIS_KEY_WA = "bridge:map:wa_to_ds"

    async def initialize(self):
        """
        1. Lee el JSON local.
        2. Lo carga en Redis (para asegurar que la DB tenga lo último del repo).
        """
        if not os.path.exists(self.config_path):
            print(f"No hay mapping.json, se usará solo lo que haya en Redis.")
            return

        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)


        # Preparamos los diccionarios para subirlos a Redis en lote
        # Redis guarda todo como string, así que normalizamos
        ds_to_wa = {str(k): v for k, v in raw_data.items()}
        wa_to_ds = {v: k for k, v in raw_data.items()}
        print(f"ds_to_wa: {ds_to_wa}")
        print(f"wa_to_ds: {wa_to_ds}")

        # Limpiamos y cargamos de nuevo (por si borraste algo en el json)
        # Usamos pipeline para que sea atómico y rápido
        async with r.pipeline() as pipe:
            await pipe.delete(self.REDIS_KEY_DS)
            await pipe.delete(self.REDIS_KEY_WA)
            if ds_to_wa:
                await pipe.hset(self.REDIS_KEY_DS, mapping=ds_to_wa)
                await pipe.hset(self.REDIS_KEY_WA, mapping=wa_to_ds)
            await pipe.execute()
        
        print("[Router] Mapeo sincronizado JSON -> Redis")

    async def resolve(self, origin):
        """
        El método mágico bidireccional, ahora consultando a Redis.
        - Si entra INT (Discord ID) -> Busca en hash DS
        - Si entra STR (WhatsApp Name) -> Busca en hash WA
        """
        if isinstance(origin, int):
            # Caso Discord -> WA
            # Redis devuelve string, lo devolvemos directo
            return await r.hget(self.REDIS_KEY_DS, str(origin))
            
        elif isinstance(origin, str):
            # Caso WA -> Discord
            # Redis devuelve string, hay que convertir a INT para Discord
            result = await r.hget(self.REDIS_KEY_WA, origin)
            return int(result) if result else None
            
        return None

    # Métodos explícitos por si los necesitás
    async def add_route(self, discord_id: int, wa_name: str):
        """Permite agregar rutas dinámicamente sin tocar el JSON"""
        await r.hset(self.REDIS_KEY_DS, str(discord_id), wa_name)
        await r.hset(self.REDIS_KEY_WA, wa_name, str(discord_id))

# Instancia global
router = AsyncRouter(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapping.json"))