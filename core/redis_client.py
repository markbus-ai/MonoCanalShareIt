import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

# Creamos un pool de conexiones asíncrono
redis_pool = redis.ConnectionPool(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True # Clave para que devuelva strings y no bytes
)

# Instancia global que importaremos en los otros archivos
r = redis.Redis(connection_pool=redis_pool) 