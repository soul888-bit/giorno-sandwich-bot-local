import os
import json
import asyncio
import aiohttp
import ssl
import certifi
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)

load_dotenv()

# Configurations .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
WALLET_PRIVATE_KEY = json.loads(os.getenv("PRIVATE_KEY"))
SOLANA_PUBLIC_ADDRESS = os.getenv("SOLANA_PUBLIC_ADDRESS")

SLIPPAGE_MAX = float(os.getenv("SLIPPAGE_MAX", 4))
FIXED_BET = float(os.getenv("FIXED_BET", 0.2))
MIN_SWAP_AMOUNT = float(os.getenv("MIN_SWAP_AMOUNT", 0.4))
MIN_NET_PROFIT = float(os.getenv("MIN_NET_PROFIT", 5))
PRIORITY_FEE = float(os.getenv("PRIORITY_FEE", 0.0005))
DEX_ALLOWED = os.getenv("DEX_ALLOWED", "orca,meteora").split(",")

ssl_context = ssl.create_default_context(cafile=certifi.where())
watched_tokens = {}
user_settings = {
    "slippage": SLIPPAGE_MAX,
    "bet": FIXED_BET,
    "min_swap": MIN_SWAP_AMOUNT,
    "min_profit": MIN_NET_PROFIT,
    "priority_fee": PRIORITY_FEE
}
SELECTING_SETTING = 0

# Telegram alert
async def send_alert(message: str):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        await session.post(url, json=payload)

# Fonctions Telegram Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        *[[InlineKeyboardButton(f"{token} : {'ON' if info['active'] else 'OFF'}", callback_data=f"toggle_{token}")]
          for token, info in watched_tokens.items()],
        [InlineKeyboardButton("Pause All", callback_data="pause_all"), InlineKeyboardButton("Resume All", callback_data="resume_all")],
        [InlineKeyboardButton("/settings", callback_data="settings")]
    ]
    if update.message:
        await update.message.reply_text(
            "🎛 Menu principal :", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "🎛 Menu principal :", reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"Slippage max : {user_settings['slippage']}%", callback_data="slippage")],
        [InlineKeyboardButton(f"Mise fixe : {user_settings['bet']} SOL", callback_data="bet")],
        [InlineKeyboardButton(f"Swap min : {user_settings['min_swap']} SOL", callback_data="min_swap")],
        [InlineKeyboardButton(f"Profit min : {user_settings['min_profit']} $", callback_data="min_profit")],
        [InlineKeyboardButton(f"Priority fee : {user_settings['priority_fee']} SOL", callback_data="priority_fee")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text("Réglages :", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Réglages :", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_SETTING

async def setting_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['setting_to_change'] = query.data
    messages = {
        "slippage": "Changer le slippage max (%) :",
        "bet": "Changer la mise fixe (SOL) :",
        "min_swap": "Changer le montant min d’un swap ciblé (SOL) :",
        "min_profit": "Changer le profit net minimum ($) :",
        "priority_fee": "Changer la priority fee (SOL) :"
    }
    await query.edit_message_text(messages[query.data])
    return SELECTING_SETTING

async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('setting_to_change')
    value = update.message.text
    try:
        user_settings[key] = float(value)
        await update.message.reply_text(f"✅ Réglage modifié : {key} = {value}")
    except ValueError:
        await update.message.reply_text("❌ Entrée invalide.")
    return ConversationHandler.END

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage : /add <token_address>")
        return
    token = context.args[0]
    watched_tokens[token] = {"active": True}
    await update.message.reply_text(f"✅ Token ajouté : {token}")

async def delete_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage : /delete <token_address>")
        return
    token = context.args[0]
    if token in watched_tokens:
        del watched_tokens[token]
        await update.message.reply_text(f"🗑 Token supprimé : {token}")
    else:
        await update.message.reply_text("❌ Token non trouvé.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watched_tokens.clear()
    await update.message.reply_text("🔁 Surveillance réinitialisée.")

async def toggle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.callback_query.data.replace("toggle_", "")
    if token in watched_tokens:
        watched_tokens[token]["active"] = not watched_tokens[token]["active"]
        await update.callback_query.answer(f"{token} {'activé' if watched_tokens[token]['active'] else 'désactivé'}")
    await start(update, context)

async def pause_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for token in watched_tokens:
        watched_tokens[token]["active"] = False
    await update.callback_query.answer("⏸ Tous les tokens en pause")
    await start(update, context)

async def resume_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for token in watched_tokens:
        watched_tokens[token]["active"] = True
    await update.callback_query.answer("▶️ Tous les tokens réactivés")
    await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start – Menu principal\n"
        "/add <token_address> – Ajouter un token\n"
        "/delete <token_address> – Supprimer un token\n"
        "/reset – Réinitialiser la surveillance\n"
        "/settings – Modifier les paramètres\n"
        "/help – Aide"
    )

# Analyse opportunité
async def is_profitable_swap(event: dict) -> bool:
    try:
        token = event.get("token", {}).get("mint")
        amount_in = float(event.get("nativeInputAmount", 0)) / 1e9
        dex = event.get("events", {}).get("swap", {}).get("source")

        if token not in watched_tokens or not watched_tokens[token]["active"]:
            return False

        if amount_in >= MIN_SWAP_AMOUNT and dex in DEX_ALLOWED:
            estimated_profit = round(FIXED_BET * 0.1 * (SLIPPAGE_MAX / 100), 2)
            return estimated_profit >= MIN_NET_PROFIT
    except Exception as e:
        print("Erreur analyse swap:", e)
    return False

# Webhook Helius
app = FastAPI()

@app.post("/webhook")
async def webhook_listener(request: Request):
    body = await request.json()
    print("📥 Webhook reçu :", json.dumps(body, indent=2))

    for event in body:
        if event.get("type") == "SWAP":
            if await is_profitable_swap(event):
                token = event.get("token", {}).get("mint")
                amount = float(event.get("nativeInputAmount", 0)) / 1e9
                await send_alert(
                    f"🥪 Opportunité repérée sur ${token}\nSwap : {amount:.2f} SOL"
                )
                # TODO : Insérer ici la logique de frontrun/backrun

    return JSONResponse(content={"status": "ok"})

# Lancer bot Telegram
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        CallbackQueryHandler(settings, pattern="^settings$")
    ],
    states={
        SELECTING_SETTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_value),
            CallbackQueryHandler(setting_selected)
        ]
    },
    fallbacks=[]
)

telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CommandHandler("add", add_token))
telegram_app.add_handler(CommandHandler("delete", delete_token))
telegram_app.add_handler(CommandHandler("reset", reset))
telegram_app.add_handler(CommandHandler("settings", settings))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(toggle_token, pattern="^toggle_"))
telegram_app.add_handler(CallbackQueryHandler(pause_all, pattern="^pause_all$"))
telegram_app.add_handler(CallbackQueryHandler(resume_all, pattern="^resume_all$"))

@app.on_event("startup")
async def on_startup():
    print("\n✅ Giorno Sandwich Bot & Webhook démarrés\n")
    await telegram_app.initialize()
    await telegram_app.start()
    asyncio.create_task(telegram_app.updater.start_polling())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
