
import aiohttp
import os
from telegram import Update, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
import json

MULTIPLAYER_API_URL = os.getenv("MULTIPLAYER_API_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL")

async def create_multiplayer_room(quiz_id: str, quiz_data: dict, creator_id: int) -> dict:
    """Create a multiplayer room via API"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MULTIPLAYER_API_URL}/api/create-room",
            json={
                "quiz_id": quiz_id,
                "quiz_data": quiz_data,
                "creator_id": creator_id
            }
        ) as response:
            return await response.json()



async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the web app (e.g. export results)."""
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except Exception:
        return

    action = data.get("action")

    if action == "export_results":
        text = data.get("text", "No results available.")
        room_id = data.get("room_id", "")

        # Send results as a formatted message to the user
        await update.effective_message.reply_text(
            f"📊 <b>Battle Results Exported</b>\n"
            f"Room: <code>{room_id}</code>\n\n"
            f"<pre>{text}</pre>",
            parse_mode="HTML"
        )
