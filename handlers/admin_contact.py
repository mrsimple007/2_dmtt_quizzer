import os
import logging
from datetime import datetime
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    filters, ContextTypes
)
from telegram.constants import ParseMode
from src.imports import *

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

active_conversations: Dict[int, Dict] = {}
CONTENT = 1

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "999932510")


async def send_payment_request_to_admin(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    amount_uzs: int,
    is_custom: bool = False
) -> None:
    """Send payment request to admin without deleting previous messages"""
    try:
        if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == "YOUR_ADMIN_CHAT_ID":
            logger.warning("Admin chat ID not configured")
            return

        # Create payment request message
        payment_type = "Custom" if is_custom else "Standard"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        admin_message = (
            f"💳 <b>New Payment Request</b>\n"
            f"📅 Time: {timestamp}\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"👤 Name: {user_name}\n"
            f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
            f"🏷️ Type: {payment_type}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Create inline keyboard for admin actions
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve Payment", 
                    callback_data=f"approve_payment_{user_id}_{amount_uzs}"
                ),
                InlineKeyboardButton(
                    "❌ Decline Payment", 
                    callback_data=f"decline_payment_{user_id}_{amount_uzs}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Contact User", 
                    callback_data=f"contact_user_{user_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message to admin (new message, don't edit/delete previous ones)
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # Store conversation context
        active_conversations[user_id] = {
            "thread_id": None,
            "last_activity": datetime.now(),
            "context": "payment_request",
            "amount": amount_uzs
        }
        
        logger.info(f"Payment request sent to admin for user {user_id}, amount {amount_uzs} UZS")
        
    except Exception as e:
        logger.error(f"Failed to send payment request to admin: {e}")


async def handle_admin_payment_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    query = update.callback_query
    await query.answer()
    
    try:
        from src.user_management import add_balance
        _, _, user_id_str, amount_str = query.data.split("_")
        user_id = int(user_id_str)
        amount_uzs = int(amount_str)
        amount_kopecks = amount_uzs * 100
        
        # Add balance to user
        success = await add_balance(user_id, amount_kopecks)
        
        if success:
            # Update admin message to show approval
            approved_message = (
                f"✅ <b>Payment Approved</b>\n"
                f"{query.message.text}\n"
                f"💚 Status: <b>APPROVED</b>\n"
                f"⏰ Approved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await query.edit_message_text(
                text=approved_message,
                parse_mode=ParseMode.HTML
            )
            
            # Notify user about successful payment
            try:
                from src.user_management import get_user_language
                user_lang = await get_user_language(user_id)
                success_message = (
                    f"✅ <b>Payment Confirmed!</b>\n\n"
                    f"💰 Amount: <b>{amount_uzs} UZS</b> has been added to your balance.\n"
                    f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"Thank you for your payment! 🎉"
                )
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=success_message,
                    parse_mode=ParseMode.HTML
                )
                
            except Exception as e:
                logger.error(f"Failed to notify user {user_id} about payment approval: {e}")
            
        else:
            await query.edit_message_text(
                text=f"❌ Error: Failed to add balance to user {user_id}",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error in handle_admin_payment_approval: {e}")
        await query.edit_message_text(
            text="❌ Error processing payment approval",
            parse_mode=ParseMode.HTML
        )


async def handle_admin_payment_decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin decline of payment requests"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    
    try:
        # Parse callback data: decline_payment_{user_id}_{amount}
        _, _, user_id_str, amount_str = query.data.split("_")
        user_id = int(user_id_str)
        amount_uzs = int(amount_str)
        
        # Update admin message to show decline
        declined_message = (
            f"❌ <b>Payment Declined</b>\n"
            f"{query.message.text}\n"
            f"🔴 Status: <b>DECLINED</b>\n"
            f"⏰ Declined at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await query.edit_message_text(
            text=declined_message,
            parse_mode=ParseMode.HTML
        )
        
        # Notify user about payment decline
        try:
            user_lang = await get_user_language(user_id)
            decline_message = (
                f"❌ <b>Payment Issue</b>\n\n"
                f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
                f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Your payment could not be processed. Please contact support for assistance."
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=decline_message,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about payment decline: {e}")
            
    except Exception as e:
        logger.error(f"Error in handle_admin_payment_decline: {e}")
        await query.edit_message_text(
            text="❌ Error processing payment decline",
            parse_mode=ParseMode.HTML
        )


async def handle_admin_contact_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin initiating contact with user"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Parse callback data: contact_user_{user_id}
        _, _, user_id_str = query.data.split("_")
        user_id = int(user_id_str)
        
        # Create thread for this conversation
        thread_message = await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"💬 <b>Conversation with User {user_id}</b>\n\nReply to this message to send messages to the user.",
            parse_mode=ParseMode.HTML
        )
        
        # Store conversation context
        active_conversations[user_id] = {
            "thread_id": thread_message.message_id,
            "last_activity": datetime.now(),
            "context": "admin_initiated"
        }
            
    except Exception as e:
        logger.error(f"Error in handle_admin_contact_user: {e}")


async def handle_admin_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        return
    
    message = update.message
    if not message.reply_to_message:
        return
    
    # Find which user this reply is for
    replied_message_id = message.reply_to_message.message_id
    target_user_id = None
    
    for user_id, conv_data in active_conversations.items():
        if conv_data.get("thread_id") == replied_message_id:
            target_user_id = user_id
            break
    
    if not target_user_id:
        return
    
    try:
        # Forward admin message to user
        admin_message = (
            f"👨‍💼 <b>Admin Reply</b>\n\n"
            f"{message.text}\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        sent_message = await context.bot.send_message(
            chat_id=target_user_id,
            text=admin_message,
            parse_mode=ParseMode.HTML
        )
        
        # Update conversation activity
        active_conversations[target_user_id]["last_activity"] = datetime.now()
        
        # Confirm to admin that message was sent
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Message sent to user {target_user_id}",
            reply_to_message_id=message.message_id
        )
        
    except Exception as e:
        logger.error(f"Failed to send admin reply to user {target_user_id}: {e}")
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"❌ Failed to send message to user {target_user_id}",
            reply_to_message_id=message.message_id
        )


async def handle_user_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    if not update.effective_user:
            return 

    user_id = update.effective_user.id
    message = update.message
    
    # Check if user has an active conversation with admin
    if user_id not in active_conversations:
        return
    
    conv_data = active_conversations[user_id]
    
    try:
        # Prepare user message for admin
        user_message = (
            f"👤 <b>User {user_id} ({update.effective_user.full_name})</b>\n\n"
            f"{message.text}\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if conv_data.get("thread_id"):
            # Reply to the existing thread
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=user_message,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=conv_data["thread_id"]
            )
        else:
            # Create new thread
            thread_message = await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"💬 <b>Message from User {user_id}</b>\n\n{user_message}",
                parse_mode=ParseMode.HTML
            )
            active_conversations[user_id]["thread_id"] = thread_message.message_id
        
        # Update last activity
        active_conversations[user_id]["last_activity"] = datetime.now()
        
        # Confirm to user that message was sent
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Your message has been sent to our support team. We'll respond shortly!",
            reply_to_message_id=message.message_id
        )
        
    except Exception as e:
        logger.error(f"Failed to send user message to admin: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Failed to send your message to support. Please try again later.",
            reply_to_message_id=message.message_id
        )


def setup_admin_contact_handlers(application: Application) -> None:
    """Setup all handlers for admin-user communication"""
    
    # Admin handlers for payment actions
    application.add_handler(CallbackQueryHandler(
        handle_admin_payment_approval, 
        pattern="^approve_payment_[0-9]+_[0-9]+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_admin_payment_decline, 
        pattern="^decline_payment_[0-9]+_[0-9]+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_admin_contact_user, 
        pattern="^contact_user_[0-9]+$"
    ))
    
    # Handler for admin replies (only in admin chat)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.REPLY & filters.Chat(chat_id=int(ADMIN_CHAT_ID)),
        handle_admin_reply_to_user
    ))
    
    # Handler for user messages to admin (check if they have active conversations)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Chat(chat_id=int(ADMIN_CHAT_ID)),
        handle_user_message_to_admin
    ))


async def start_conversation_with_admin(user_id: int, context: str = "general") -> None:
    """Start a new conversation thread with admin"""
    active_conversations[user_id] = {
        "thread_id": None,
        "last_activity": datetime.now(),
        "context": context
    }


async def end_conversation_with_admin(user_id: int) -> None:
    """End conversation thread with admin"""
    if user_id in active_conversations:
        del active_conversations[user_id]


async def is_user_in_conversation(user_id: int) -> bool:
    """Check if user has an active conversation with admin"""
    return user_id in active_conversations


async def cleanup_old_conversations(max_age_hours: int = 24) -> None:
    """Clean up old conversation threads"""
    current_time = datetime.now()
    expired_users = []
    
    for user_id, conv_data in active_conversations.items():
        time_diff = current_time - conv_data["last_activity"]
        if time_diff.total_seconds() > (max_age_hours * 3600):
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del active_conversations[user_id]
        logger.info(f"Cleaned up expired conversation for user {user_id}")


# Command handlers for manual conversation management
async def admin_list_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all active conversations"""
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        return
    
    if not active_conversations:
        await update.message.reply_text("No active conversations.")
        return
    
    conversation_list = "📋 <b>Active Conversations:</b>\n\n"
    for user_id, conv_data in active_conversations.items():
        last_activity = conv_data["last_activity"].strftime('%Y-%m-%d %H:%M:%S')
        context_info = conv_data.get("context", "general")
        conversation_list += (
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📅 Last Activity: {last_activity}\n"
            f"🏷️ Context: {context_info}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    await update.message.reply_text(
        conversation_list,
        parse_mode=ParseMode.HTML
    )


async def admin_end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to end a specific conversation"""
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /end_conversation <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        await end_conversation_with_admin(user_id)
        await update.message.reply_text(f"✅ Ended conversation with user {user_id}")
    except (ValueError, KeyError):
        await update.message.reply_text("❌ Invalid user ID or conversation not found")


def setup_admin_commands(application: Application) -> None:
    application.add_handler(CommandHandler("conversations", admin_list_conversations))
    application.add_handler(CommandHandler("end_conversation", admin_end_conversation))


async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    context.user_data["admin_contact_mode"] = True
    
    from src.user_management import get_user_language
    language = await get_user_language(user.id)
    from handlers.admin_contact import start_conversation_with_admin
    await start_conversation_with_admin(user.id, context="feedback")
    from src.prompts_summarize import get_admin_message
    msg = get_admin_message(language, "admin_contact_started")
    await query.answer()
    
    # Send a new message instead of editing the existing one
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=msg,
        parse_mode=ParseMode.HTML
    )
    return CONTENT