#!/usr/bin/env python3
"""
MonoCanalShareIt - Main Entry Point
Ejecuta simultáneamente el Discord Bot y el WhatsApp Worker
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MonoCanalShareIt')

from discord_bot.bot import bot
from wa_worker.worker import main as wa_worker_main
from core.redis_client import r
from core.routing import AsyncRouter

async def check_redis_connection():
    """Verifica que Redis esté disponible"""
    try:
        await r.ping()
        logger.info("✅ Conexión a Redis establecida")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")
        return False

async def run_discord_bot():
    """Ejecuta el bot de Discord"""
    try:
        TOKEN = os.getenv('DISCORD_TOKEN')
        if not TOKEN:
            logger.error("DISCORD_TOKEN no configurado en .env")
            raise ValueError("DISCORD_TOKEN no configurado en .env")
        
        logger.info("🤖 Iniciando Discord Bot...")
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"❌ Error en Discord Bot: {e}")
        raise

async def run_whatsapp_worker():
    """Ejecuta el worker de WhatsApp"""
    try:
        logger.info("📱 Iniciando WhatsApp Worker...")
        await wa_worker_main()
    except Exception as e:
        logger.error(f"❌ Error en WhatsApp Worker: {e}")
        raise

async def main():
    """Punto de entrada principal"""
    logger.info("MonoCanalShareIt - Iniciando")

    
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', '6379')
    logger.info(f"Redis: {redis_host}:{redis_port}")
    
    # Verificar conexión a Redis (con reintentos)
    max_retries = 5
    for attempt in range(max_retries):
        if await check_redis_connection():
            break
        logger.warning(f"⏳ Reintentando conexión a Redis ({attempt + 1}/{max_retries})...")
        await asyncio.sleep(2)
    else:
        logger.error("No se pudo conectar a Redis después de varios intentos.")
        sys.exit(1)
    
    # Inicializar el router de mapping
    try:
        router = AsyncRouter(config_path="core/mapping.json")
        await router.initialize()
        logger.info("✅ Router de mapping inicializado")
    except Exception as e:
        logger.error(f"Error inicializando router: {e}")
        # No es crítico, continúa sin mapping
    
    # Ejecutar Discord Bot y WhatsApp Worker en paralelo
    try:
        await asyncio.gather(
            run_discord_bot(),
            run_whatsapp_worker(),
            return_exceptions=True
        )
    except KeyboardInterrupt:
        logger.info("\n⏹️  Deteniendo aplicación...")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Aplicación terminada por el usuario")
        sys.exit(0)
