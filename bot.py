import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, JSONResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import uvicorn

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
# Render asigna automáticamente esta variable con la URL de tu servicio
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 8000))

if not TOKEN:
    raise ValueError("No se encontró BOT_TOKEN en variables de entorno")
if not RENDER_URL:
    raise ValueError("No se encontró RENDER_EXTERNAL_URL (¿estás en Render?)")

# --- Handlers de Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ¡Hola! Soy tu bot de juegos.\n\n"
        "Comandos disponibles:\n"
        "/jugar - Empezar a jugar\n"
        "/comprar - Comprar vidas extras"
    )

async def jugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 ¡A jugar! (lógica del juego aquí)")

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Opciones de compra próximamente...")

# --- Configuración del bot ---
async def setup_webhook(app: Application) -> None:
    """Configura el webhook al iniciar"""
    webhook_url = f"{RENDER_URL}/webhook"
    
    # Eliminar webhook anterior (por si acaso)
    await app.bot.delete_webhook()
    
    # Configurar el nuevo webhook
    await app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES
    )
    
    # Verificar que quedó bien configurado
    webhook_info = await app.bot.get_webhook_info()
    logger.info(f"Webhook configurado en: {webhook_info.url}")
    logger.info(f"Pending updates: {webhook_info.pending_update_count}")

# --- Servidor web ---
async def startup_event():
    """Se ejecuta cuando arranca el servidor"""
    logger.info("Iniciando bot...")
    # La app de Telegram se pasa como estado en el request

async def shutdown_event():
    """Se ejecuta cuando se apaga el servidor"""
    logger.info("Apagando bot...")

async def webhook_handler(request: Request) -> JSONResponse:
    """Recibe las actualizaciones de Telegram"""
    # La app de Telegram está guardada en request.state
    app = request.state.telegram_app
    
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Error procesando update: {e}")
        return JSONResponse({"ok": False}, status_code=500)

async def health_check(request: Request) -> PlainTextResponse:
    """Endpoint para Render (health check)"""
    return PlainTextResponse("OK")

# --- Función principal ---
async def main():
    # Crear aplicación de Telegram
    telegram_app = Application.builder().token(TOKEN).updater(None).build()
    
    # Registrar comandos
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("jugar", jugar))
    telegram_app.add_handler(CommandHandler("comprar", comprar))
    
    # Configurar webhook
    await setup_webhook(telegram_app)
    
    # Crear app Starlette
    starlette_app = Starlette(
        routes=[
            Route("/", health_check),  # Health check en la raíz
            Route("/webhook", webhook_handler, methods=["POST"]),
            Route("/health", health_check),  # Health check alternativo
        ],
        on_startup=[startup_event],
        on_shutdown=[shutdown_event]
    )
    
    # Guardar la app de Telegram en el estado de Starlette para accederla en los handlers
    @starlette_app.middleware("http")
    async def add_telegram_app(request: Request, call_next):
        request.state.telegram_app = telegram_app
        response = await call_next(request)
        return response
    
    # Iniciar servidor
    config = uvicorn.Config(
        starlette_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Iniciar la app de Telegram y el servidor
    async with telegram_app:
        await telegram_app.start()
        await server.serve()
        await telegram_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
