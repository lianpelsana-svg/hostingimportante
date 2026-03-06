import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import uvicorn

# Importar funciones de base de datos
from database import (
    init_db, registrar_usuario, usar_vida, sumar_vidas,
    obtener_vidas, activar_premium, guardar_pago
)

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 8000))

if not TOKEN:
    raise ValueError("No se encontró BOT_TOKEN")
if not RENDER_URL:
    raise ValueError("No se encontró RENDER_EXTERNAL_URL")

# Inicializar base de datos al arrancar
init_db()
logger.info("Base de datos lista")

# --- Handlers de Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registrar_usuario(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"🤖 ¡Hola {user.first_name}! Bienvenido al Bot de Juegos.\n\n"
        "Comandos disponibles:\n"
        "/jugar - Jugar una partida (consume 1 vida)\n"
        "/vidas - Ver cuántas vidas te quedan\n"
        "/comprar - Comprar más vidas o suscripción premium\n"
        "/premium - Información sobre premium"
    )

async def vidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vidas = obtener_vidas(user_id)
    await update.message.reply_text(f"🎮 Te quedan {vidas} vidas.")

async def jugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    puede, mensaje = usar_vida(user_id)
    
    if puede:
        if mensaje == "premium":
            await update.message.reply_text(
                "🎮 ¡Comienzas tu partida! (Modo premium)\n\n"
                "¿Qué querés jugar?\n"
                "/adivinar - Adivina el número"
            )
        else:
            await update.message.reply_text(
                f"🎮 ¡Comienzas tu partida! {mensaje}\n\n"
                "¿Qué querés jugar?\n"
                "/adivinar - Adivina el número"
            )
    else:
        # Ofrecer comprar vidas
        keyboard = [
            [InlineKeyboardButton("💳 Comprar 10 vidas (1 USDT)", callback_data="comprar_10_vidas")],
            [InlineKeyboardButton("🌟 Suscripción premium (5 USDT/mes)", callback_data="comprar_premium")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "😢 Te quedaste sin vidas. ¿Quieres seguir jugando?",
            reply_markup=reply_markup
        )

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra opciones de compra"""
    keyboard = [
        [InlineKeyboardButton("💳 10 vidas (1 USDT)", callback_data="comprar_10_vidas")],
        [InlineKeyboardButton("🌟 Premium 30 días (5 USDT)", callback_data="comprar_premium")],
        [InlineKeyboardButton("🇦🇷 Pagar con Mercado Pago (ARS)", callback_data="pagar_mp")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💰 Elegí tu método de pago:",
        reply_markup=reply_markup
    )

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Información sobre premium"""
    await update.message.reply_text(
        "🌟 *Plan Premium*\n\n"
        "Beneficios:\n"
        "• Vidas ilimitadas\n"
        "• Acceso a juegos exclusivos\n"
        "• Sin publicidad\n\n"
        "Precio: 5 USDT / mes (o equivalente en ARS)\n\n"
        "Usá /comprar para adquirirlo.",
        parse_mode="Markdown"
    )

# --- Handlers de juego (ejemplo) ---
import random
juegos_activos = {}

async def adivinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # No consume vida extra, ya se gastó al hacer /jugar
    numero = random.randint(1, 10)
    juegos_activos[user_id] = numero
    await update.message.reply_text(
        "🎲 Pensé un número del 1 al 10. Usá /respuesta <número> para adivinar."
    )

async def respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in juegos_activos:
        await update.message.reply_text("Primero usá /adivinar para empezar una partida.")
        return
    
    try:
        guess = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usá: /respuesta 5 (con un número)")
        return
    
    secreto = juegos_activos[user_id]
    if guess == secreto:
        # Ganó: dar 3 vidas de premio
        nuevas = sumar_vidas(user_id, 3)
        await update.message.reply_text(f"🎉 ¡Correcto! Ganaste 3 vidas. Ahora tenés {nuevas} vidas.")
        del juegos_activos[user_id]
    else:
        pista = "mayor" if guess < secreto else "menor"
        await update.message.reply_text(f"❌ No, es {pista}. Seguí intentando.")

# --- Callbacks para botones (pagos) ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    if data == "comprar_10_vidas":
        # Aquí iría la integración con Binance Pay
        # Por ahora solo simulamos
        await query.edit_message_text(
            "⚙️ Integración de pagos en desarrollo.\n"
            "Próximamente podrás pagar con Binance Pay (USDT)."
        )
        # Cuando esté listo, llamar a generar_pago_binance()
        
    elif data == "comprar_premium":
        await query.edit_message_text(
            "⚙️ Integración de pagos en desarrollo.\n"
            "Próximamente podrás suscribirte con Binance Pay (USDT)."
        )
        
    elif data == "pagar_mp":
        await query.edit_message_text(
            "⚙️ Integración con Mercado Pago en desarrollo.\n"
            "Próximamente podrás pagar en ARS."
        )

# --- Configuración del webhook ---
async def setup_webhook(app: Application) -> None:
    webhook_url = f"{RENDER_URL}/webhook"
    await app.bot.delete_webhook()
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    webhook_info = await app.bot.get_webhook_info()
    logger.info(f"Webhook configurado en: {webhook_info.url}")

# --- Servidor web (Starlette) ---
async def webhook_handler(request: Request) -> JSONResponse:
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
    return PlainTextResponse("OK")

# --- Inicialización y ejecución ---
async def main():
    # Crear aplicación de Telegram
    telegram_app = Application.builder().token(TOKEN).updater(None).build()
    
    # Registrar comandos
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("vidas", vidas))
    telegram_app.add_handler(CommandHandler("jugar", jugar))
    telegram_app.add_handler(CommandHandler("comprar", comprar))
    telegram_app.add_handler(CommandHandler("premium", premium))
    telegram_app.add_handler(CommandHandler("adivinar", adivinar))
    telegram_app.add_handler(CommandHandler("respuesta", respuesta))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    
    # Configurar webhook
    await setup_webhook(telegram_app)
    
    # Crear app Starlette
    starlette_app = Starlette(
        routes=[
            Route("/", health_check),
            Route("/health", health_check),
            Route("/webhook", webhook_handler, methods=["POST"]),
        ]
    )
    
    # Pasar la app de Telegram a los handlers
    @starlette_app.middleware("http")
    async def add_telegram_app(request: Request, call_next):
        request.state.telegram_app = telegram_app
        return await call_next(request)
    
    # Iniciar servidor
    config = uvicorn.Config(
        starlette_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    async with telegram_app:
        await telegram_app.start()
        await server.serve()
        await telegram_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
