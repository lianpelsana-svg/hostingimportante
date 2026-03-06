import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuración básica
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")  # Lo configuraremos en Render
URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render crea esta variable automáticamente
PORT = 8000

# --- Handlers de Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde al comando /start"""
    await update.message.reply_text(
        "🤖 ¡Hola! Soy tu bot de juegos.\n\n"
        "Comandos disponibles:\n"
        "/jugar - Empezar a jugar\n"
        "/comprar - Comprar vidas extras\n"
        "/premium - Información sobre suscripción"
    )

async def jugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para jugar (ejemplo)"""
    await update.message.reply_text("🎮 Acá iría la lógica de tu juego...")

# --- Función principal ---
async def main():
    # Crear la aplicación de Telegram
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jugar", jugar))
    # Acá agregarías más comandos: /comprar, /premium, etc.
    
    # Configurar el webhook (la URL que Telegram usará para avisarnos)
    webhook_url = f"{URL}/telegram"
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logging.info(f"Webhook configurado en {webhook_url}")
    
    # --- Servidor web Starlette para recibir los webhooks ---
    async def telegram(request: Request) -> Response:
        """Recibe las actualizaciones de Telegram"""
        await app.update_queue.put(Update.de_json(await request.json(), app.bot))
        return Response()
    
    async def health(request: Request) -> PlainTextResponse:
        """Endpoint para que Render verifique que el servicio está vivo"""
        return PlainTextResponse("OK")
    
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram, methods=["POST"]),
        Route("/healthcheck", health, methods=["GET"]),
    ])
    
    # Ejecutar el servidor web
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(
        starlette_app, 
        host="0.0.0.0", 
        port=PORT, 
        log_level="info"
    ))
    
    async with app:
        await app.start()
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
