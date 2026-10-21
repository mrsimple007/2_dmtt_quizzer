from src.tables import TBL
import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut, NetworkError
from supabase import create_client, Client
from src.prompts_summarize import TRANSLATIONS
from src.imports import ADMIN_CHAT_ID, ADMIN_USERNAME, CARD_NUMBER, CARD_NUMBER_2
from telegram import Document, PhotoSize


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
CUSTOM_AMOUNT = 1


SUPABASE_URL = os.environ.get("QUIZ_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("QUIZ_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BALANCE_AMOUNTS = {
    "1000": 1000,
    "2000": 2000,
    "3000": 3000,
    "4000": 4000,
    "5000": 5000,
    "6000": 6000,
    "9000": 9000,
    "10000": 10000,
    "12000": 12000,
    "15000": 15000,
    "20000": 20000,
    "30000": 30000,
    "40000": 40000,
    "50000": 50000,
}

from enum import Enum
class PaymentMode(Enum):
    AUTO = "auto"
    MANUAL = "manual"

# Bot identifier - set this based on your bot
BOT_ID = os.getenv("BOT_ID", "simplequizzer")  # or "simpleppt"
BOT_NAME = os.getenv("BOT_NAME", "SimpleQuizzer" if BOT_ID == "simplequizzer" else ("DMTT Quiz" if BOT_ID.startswith("dmtt") else "SimplePPT"))

MANUAL_PAYMENT_MESSAGES = {
    'uz': {
        'balance_topup': """💳 Balansni to'ldirish uchun:

💰 <b>Miqdor</b>: {amount} so'm

📋 <b>To'lov qilish tartibi</b>:
1️⃣ Quyidagi kartalardan biriga 30 daqiqa ichida {amount} so'm o'tkazing:
   <code>{card_number}</code>
   yoki
   <code>{card_number_2}</code>

2️⃣ To'lov chekini admin {ADMIN_USERNAME} ga yuboring

3️⃣ Balans admin tomonidan tasdiqlanganidan keyin to'ldiriladi

⚠️ <b>Muhim</b>: Chekni yuborishni unutmang!""",


        'payment_pending': """⏳ <b>To'lov kutilmoqda</b>

Agar to'lov amalga oshirilgan bo'lsa:
• To'lov chekini {ADMIN_USERNAME} ga yuboring
• 24 soat ichida balans to'ldiriladi

❓ Savollar bo'lsa {ADMIN_USERNAME} ga murojaat qiling"""
    },
    'ru': {
        'balance_topup': """💳 Для пополнения баланса:

💰 <b>Сумма</b>: {amount} сум

📋 <b>Порядок оплаты</b>:
1️⃣ Переведите {amount} сум на одну из карт в течение 30 минут:
   <code>{card_number}</code>
   или
   <code>{card_number_2}</code>

2️⃣ Отправьте чек оплаты админу {ADMIN_USERNAME}

3️⃣ Баланс будет пополнен после подтверждения админа

⚠️ <b>Важно</b>: Не забудьте отправить чек!""",

        'payment_pending': """⏳ <b>Ожидается оплата</b>

Если оплата уже произведена:
• Отправьте чек оплаты {ADMIN_USERNAME}
• Баланс будет пополнен в течение 24 часов

❓ Вопросы? Обращайтесь к {ADMIN_USERNAME}"""
    },
    'en': {
        'balance_topup': """💳 To top up balance:

💰 <b>Amount</b>: {amount} UZS

📋 <b>Payment procedure</b>:
1️⃣ Transfer {amount} UZS to one of the cards within 30 minutes:
   <code>{card_number}</code>
   or
   <code>{card_number_2}</code>

2️⃣ Send payment receipt to admin {ADMIN_USERNAME}

3️⃣ Balance will be topped up after admin confirmation

⚠️ <b>Important</b>: Don't forget to send the receipt!""",

        'payment_pending': """⏳ <b>Payment pending</b>

If payment has been made:
• Send payment receipt to {ADMIN_USERNAME}
• Balance will be topped up within 24 hours

❓ Questions? Contact {ADMIN_USERNAME}"""
    }
}


async def send_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /send_check command - allows users to send payment receipts directly to admin"""
    from src.user_management import get_user_language
    
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username
    user_lang = await get_user_language(user_id)
    
    instructions = {
        "uz": """📸 <b>Chek yuborish</b>

To'lov chekingizni yuboring:
- 📷 Rasm sifatida
- 📄 PDF fayl sifatida
- ✍️ Yoki matn xabar sifatida

Chekni yuborishdan oldin, to'lovni amalga oshirganingizga ishonch hosil qiling.""",
        "ru": """📸 <b>Отправка чека</b>

Отправьте ваш платёжный чек:
- 📷 Как фото
- 📄 Как PDF файл
- ✍️ Или как текстовое сообщение

Убедитесь, что вы совершили платёж перед отправкой чека.""",
        "en": """📸 <b>Send Receipt</b>

Send your payment receipt:
- 📷 As a photo
- 📄 As a PDF file
- ✍️ Or as a text message

Make sure you've made the payment before sending the receipt."""
    }
    
    await update.message.reply_text(
        instructions.get(user_lang, instructions["uz"]),
        parse_mode=ParseMode.HTML
    )
    
    # Set a flag in user_data to expect receipt
    context.user_data['awaiting_receipt'] = True


async def handle_receipt_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt submissions (photos, documents, text messages)"""
    from src.user_management import get_user_language
    from src.imports import NOTIFICATION_ADMIN_IDS
    
    if not context.user_data or not context.user_data.get('awaiting_receipt', False):
        return 
    
    message = update.message
    
    is_photo = bool(message.photo)
    is_document = bool(message.document)
    is_text = bool(message.text and not message.text.startswith('/'))
    
    # If none of these, ignore
    if not (is_photo or is_document or is_text):
        return
    
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username
    user_lang = await get_user_language(user_id)
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare admin notification message
        user_info = f"👤 User ID: <code>{user_id}</code>\n"
        user_info += f"👤 Name: {user_name}\n"
        if username:
            user_info += f"👤 Username: @{username}\n"
        
        admin_message = (
            f"📸 <b>Payment Receipt Received</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Time: {timestamp}\n"
            f"{user_info}"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Contact User", 
                    url=f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_photo:
            photo = message.photo[-1]  
            caption = message.caption or ""
            
            for admin_id in NOTIFICATION_ADMIN_IDS:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=photo.file_id,
                        caption=f"{admin_message}\n\n📝 Caption: {caption}" if caption else admin_message,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send photo receipt to admin {admin_id}: {e}")
        
        elif is_document:
            # Document receipt (PDF, etc.)
            document = message.document
            caption = message.caption or ""
            
            for admin_id in NOTIFICATION_ADMIN_IDS:
                try:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=document.file_id,
                        caption=f"{admin_message}\n\n📝 Caption: {caption}" if caption else admin_message,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send document receipt to admin {admin_id}: {e}")
        
        elif is_text:
            # Text message receipt
            text_content = message.text
            
            full_message = f"{admin_message}\n\n💬 <b>Message:</b>\n{text_content}"
            
            for admin_id in NOTIFICATION_ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=full_message,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send text receipt to admin {admin_id}: {e}")


        # Confirm to user
        confirmation = {
            "uz": f"✅ Chek muvaffaqiyatli yuborildi!\n\nAdminlar tez orada ko'rib chiqadi va balansingizni to'ldiradi. Agar bu shoshilinch bo'lsa, admin bilan bog'laning: {ADMIN_USERNAME}",
            "ru": f"✅ Чек успешно отправлен!\n\nАдмины скоро проверят и пополнят ваш баланс. Если это срочно, свяжитесь с админом: {ADMIN_USERNAME}",
            "en": f"✅ Receipt sent successfully!\n\nAdmins will review it soon and top up your balance. If it's urgent, contact the admin: {ADMIN_USERNAME}"
        }

        await message.reply_text(
            confirmation.get(user_lang, confirmation["uz"]),
            parse_mode=ParseMode.HTML
        )
        
        # Clear the awaiting flag
        context.user_data['awaiting_receipt'] = False
        
        logger.info(f"Receipt submitted by user {user_id} ({username or 'no username'})")
        
    except Exception as e:
        logger.error(f"Error in handle_receipt_submission: {e}")
        error_msg = {
            "uz": f"❌ Chekni yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring. Agar muammo davom etsa, admin bilan bog'laning: {ADMIN_USERNAME}",
            "ru": f"❌ Ошибка при отправке чека. Пожалуйста, попробуйте снова. Если проблема сохраняется, свяжитесь с админом: {ADMIN_USERNAME}",
            "en": f"❌ Error sending receipt. Please try again. If the issue persists, contact the admin: {ADMIN_USERNAME}"
        }
        await message.reply_text(
            error_msg.get(user_lang, error_msg["uz"])
        )


async def send_payment_request_to_admin(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    amount_uzs: int,
    is_custom: bool = False,
    username: str = None,
    is_subscription: bool = False,       # NEW
    subscription_plan: str = None        # NEW
) -> None:
    from src.imports import NOTIFICATION_ADMIN_IDS
    
    try:
        if not NOTIFICATION_ADMIN_IDS:
            logger.warning("No notification admin IDs configured")
            return

        # Determine payment type — NO longer auto-detecting by amount
        if is_subscription and subscription_plan:
            from handlers.premium import get_plan_name
            payment_type = f"🌟 Subscription ({get_plan_name(subscription_plan, 'en')})"
        elif is_custom:
            payment_type = "Custom"
        else:
            payment_type = "Standard"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        user_info = f"👤 User ID: <code>{user_id}</code>\n"
        user_info += f"👤 Name: {user_name}\n"
        if username:
            user_info += f"👤 Username: @{username}\n"
        
        admin_message = (
            f"💳 <b>New Payment Request</b>\n"
            f"📅 Time: {timestamp}\n"
            f"{user_info}"
            f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
            f"🏷️ Type: {payment_type}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Only approve/decline buttons
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
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        payment_key = f"payment_{user_id}_{amount_uzs}"
        context.bot_data[payment_key] = {
            'messages': {},
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'is_subscription': is_subscription,
            'subscription_plan': subscription_plan
        }
        
        for admin_id in NOTIFICATION_ADMIN_IDS:
            try:
                sent_message = await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                context.bot_data[payment_key]['messages'][admin_id] = sent_message.message_id
                logger.info(f"✅ Payment request sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send payment request to admin {admin_id}: {e}")
        
        logger.info(f"Payment request sent to {len(NOTIFICATION_ADMIN_IDS)} admin(s) for user {user_id}, amount {amount_uzs} UZS, type: {payment_type}")
        
    except Exception as e:
        logger.error(f"Failed to send payment request to admins: {e}")

async def handle_topup_amount_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle balance top-up with manual payment instructions"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    username = query.from_user.username  # Get username
    user_lang = await get_user_language(user_id)

    amount_key = query.data.split("_")[1]

    if amount_key in BALANCE_AMOUNTS:
        amount_kopecks = BALANCE_AMOUNTS[amount_key]
        amount_uzs = amount_kopecks
        
        try:
            # Show manual payment instructions
            payment_message = MANUAL_PAYMENT_MESSAGES[user_lang]["balance_topup"].format(
                amount=int(amount_uzs),
                card_number=CARD_NUMBER,
                card_number_2=CARD_NUMBER_2,
                ADMIN_USERNAME=ADMIN_USERNAME
            )
            
            keyboard = [
                [InlineKeyboardButton(
                    f"💬 {TRANSLATIONS[user_lang].get('Send_check', 'Chekni yuborish')}", 
                    url=f"https://t.me/{ADMIN_USERNAME}"
                )],
                [InlineKeyboardButton(
                    TRANSLATIONS[user_lang].get("back", "« Back"), 
                    callback_data="topup_balance"
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                payment_message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            # Send reminder message
            reminder_messages = {
                "uz": f"⏰ 30 daqiqa ichida chekni adminga yuboring, yoki to'lovingiz tasdiqlanmaydi\n👉 {ADMIN_USERNAME} \n\nyoki /send_check buyrug'i orqali chekni rasm/pdf shaklida yuborsangiz bo'ladi.",
                "ru": f"⏰ Отправьте чек админу в течение 30 минут, иначе ваш платеж не будет подтвержден\n\n👉 {ADMIN_USERNAME} или с /send_check вы можете отправить чек в виде фото/pdf.",
                "en": f"⏰ Send the receipt to the admin within 30 minutes, otherwise your payment will not be confirmed👉 {ADMIN_USERNAME} \n\nor with /send_check you can send the receipt in photo/pdf format."
            }
            
            reminder_message = reminder_messages.get(user_lang, reminder_messages["uz"])
            
            await context.bot.send_message(
                chat_id=user_id,
                text=reminder_message,
                parse_mode=ParseMode.HTML
            )
            
            await send_payment_request_to_admin(
                context=context,
                user_id=user_id,
                user_name=user_name,
                amount_uzs=int(amount_uzs),
                is_custom=False,
                username=username,
                is_subscription=False,   # explicit
                subscription_plan=None   # explicit
            )
            
        except Exception as e:
            logger.error(f"Error in handle_topup_amount_manual: {str(e)}")
            try:
                await query.edit_message_text(
                    TRANSLATIONS[user_lang]["payment_error"]
                )
            except:
                await query.message.reply_text(
                    TRANSLATIONS[user_lang]["payment_error"]
                )


async def cancel_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel top-up process"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    user_lang = await get_user_language(query.from_user.id)
    
    try:
        await query.edit_message_text(
            TRANSLATIONS[user_lang]["topup_cancelled"]
        )
    except:
        await query.message.reply_text(
            TRANSLATIONS[user_lang]["topup_cancelled"]
        )
    
    return ConversationHandler.END


async def payment_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment pending status"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)
    
    message = MANUAL_PAYMENT_MESSAGES[user_lang]['payment_pending'].format(
        ADMIN_USERNAME=ADMIN_USERNAME  
    )
    
    keyboard = [
        [InlineKeyboardButton(
            f"💬 {TRANSLATIONS[user_lang].get('contact_admin', 'Contact Admin')}", 
            url=f"https://t.me/{ADMIN_USERNAME}"
        )],
        [InlineKeyboardButton(
            TRANSLATIONS[user_lang].get("back", "« Back"), 
            callback_data="balance"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except:
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin handler to approve payment - WITH SUBSCRIPTION DETECTION."""
    from payment_integration_new import add_balance
    from src.user_management import get_user_language
    from src.imports import NOTIFICATION_ADMIN_IDS
    
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_CHAT_ID:
        await query.answer("⛔ Access denied. Admin only.", show_alert=True)
        return
    
    try:
        # ✅ FIX: Check if this is a subscription payment FIRST
        from handlers.premium import SUBSCRIPTION_PLANS, get_plan_name, PREMIUM_TRANSLATIONS
        from src.user_management import record_subscription_payment

        parts = query.data.split("_")
        user_id = int(parts[2])
        amount_uzs = int(parts[3])
        amount_kopecks = amount_uzs * 100

        payment_key = f"payment_{user_id}_{amount_uzs}"
        payment_info = context.bot_data.get(payment_key, {})

        # Use stored flag — NOT amount-based detection
        is_subscription = payment_info.get('is_subscription', False)
        subscription_plan = payment_info.get('subscription_plan')

        if is_subscription and subscription_plan:
            # ✅ This is a SUBSCRIPTION payment
            logger.info(f"[ADMIN APPROVE] Detected subscription payment: {subscription_plan} for user {user_id}")
            
            success = await record_subscription_payment(
                user_id=user_id,
                plan_key=subscription_plan,
                amount=amount_uzs * 100,  # Convert to kopecks
                payment_method="manual"
            )
            
            if success:
                user_lang = await get_user_language(user_id)
                t = PREMIUM_TRANSLATIONS[user_lang]
                plan_name = get_plan_name(subscription_plan, user_lang)
                
                # Get subscription details
                from handlers.premium import get_user_subscription
                subscription = await get_user_subscription(user_id)
                end_date = subscription["subscription_end"].strftime("%d.%m.%Y") if subscription.get("subscription_end") else "N/A"
                
                user_message = t["subscription_active"].format(
                    plan=plan_name,
                    end_date=end_date
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
                
                # Get original payment request details
                payment_key = f"payment_{user_id}_{amount_uzs}"
                payment_info = context.bot_data.get(payment_key, {})
                
                # Get user info
                try:
                    user = await context.bot.get_chat(user_id)
                    user_name = user.first_name or f"User_{user_id}"
                    username = user.username
                except:
                    user_name = f"User_{user_id}"
                    username = None
                
                # Format timestamps
                original_time = payment_info.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                approval_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Update message for the admin who approved - SUBSCRIPTION VERSION
                admin_update = (
                    f"✅ <b>SUBSCRIPTION APPROVED</b> by @{query.from_user.username or query.from_user.first_name}\n"
                    f"🌟 <b>Premium Subscription Payment</b>\n"
                    f"📅 Request Time: {original_time}\n"
                    f"👤 User ID: <code>{user_id}</code>\n"
                    f"👤 Name: {user_name}\n"
                )
                if username:
                    admin_update += f"👤 Username: @{username}\n"
                admin_update += (
                    f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
                    f"📦 Plan: <b>{plan_name}</b>\n"
                    f"⏰ Valid until: <b>{end_date}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏰ Approved: {approval_time}"
                )
                
                await query.edit_message_text(
                    admin_update,
                    parse_mode=ParseMode.HTML
                )
                
                # Update ALL other admins' messages
                admin_messages = payment_info.get('messages', {})
                
                for admin_id, message_id in admin_messages.items():
                    if str(admin_id) != str(query.from_user.id):
                        try:
                            await context.bot.edit_message_text(
                                chat_id=admin_id,
                                message_id=message_id,
                                text=admin_update,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            logger.error(f"Failed to update message for admin {admin_id}: {e}")
                
                # Clear stored message IDs
                if payment_key in context.bot_data:
                    del context.bot_data[payment_key]
                
                await query.answer("✅ Subscription activated successfully!", show_alert=True)
            else:
                await query.answer("❌ Failed to activate subscription. Check logs.", show_alert=True)
        
        else:
            # ✅ Regular BALANCE TOP-UP payment
            logger.info(f"[ADMIN APPROVE] Regular balance top-up for user {user_id}")
            
            success = await add_balance(user_id, amount_kopecks, payment_type="balance_topup", payment_method="manual")
            
            if success:
                user_lang = await get_user_language(user_id)
                
                user_message = f"""✅ <b>To'lov tasdiqlandi!</b>

💰 Miqdor: <b>{amount_uzs} UZS</b>
Balans muvaffaqiyatli to'ldirildi.

Rahmat! 🎉"""
                
                if user_lang == "ru":
                    user_message = f"""✅ <b>Платеж подтвержден!</b>

💰 Сумма: <b>{amount_uzs} UZS</b>
Баланс успешно пополнен.

Спасибо! 🎉"""
                elif user_lang == "en":
                    user_message = f"""✅ <b>Payment Approved!</b>

💰 Amount: <b>{amount_uzs} UZS</b>
Balance successfully topped up.

Thank you! 🎉"""
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
                
                # Get original payment request details
                payment_key = f"payment_{user_id}_{amount_uzs}"
                payment_info = context.bot_data.get(payment_key, {})
                
                # Get user info
                try:
                    user = await context.bot.get_chat(user_id)
                    user_name = user.first_name or f"User_{user_id}"
                    username = user.username
                except:
                    user_name = f"User_{user_id}"
                    username = None
                
                # Format timestamps
                original_time = payment_info.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                approval_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Update message for the admin who approved - BALANCE VERSION
                admin_update = (
                    f"✅ <b>APPROVED</b> by @{query.from_user.username or query.from_user.first_name}\n"
                    f"💳 <b>Balance Top-up Payment</b>\n"
                    f"📅 Time: {original_time}\n"
                    f"👤 User ID: <code>{user_id}</code>\n"
                    f"👤 Name: {user_name}\n"
                )
                if username:
                    admin_update += f"👤 Username: @{username}\n"
                admin_update += (
                    f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
                    f"🏷️ Type: Balance Top-up\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏰ {approval_time}"
                )
                
                await query.edit_message_text(
                    admin_update,
                    parse_mode=ParseMode.HTML
                )
                
                # Update ALL other admins' messages
                admin_messages = payment_info.get('messages', {})
                
                for admin_id, message_id in admin_messages.items():
                    if str(admin_id) != str(query.from_user.id):
                        try:
                            await context.bot.edit_message_text(
                                chat_id=admin_id,
                                message_id=message_id,
                                text=admin_update,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            logger.error(f"Failed to update message for admin {admin_id}: {e}")
                
                # Clear stored message IDs
                if payment_key in context.bot_data:
                    del context.bot_data[payment_key]
                
                await query.answer("✅ Payment approved successfully!", show_alert=True)
            else:
                await query.answer("❌ Failed to add balance. Check logs.", show_alert=True)
                
    except Exception as e:
        logger.error(f"Error in approve_payment: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await query.answer("❌ Error processing payment approval", show_alert=True)

async def decline_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin handler to decline payment"""
    from src.user_management import get_user_language
    from src.imports import NOTIFICATION_ADMIN_IDS
    
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_CHAT_ID:
        await query.answer("⛔ Access denied. Admin only.", show_alert=True)
        return
    
    try:
        parts = query.data.split("_")
        user_id = int(parts[2])
        amount_uzs = int(parts[3])
        
        user_lang = await get_user_language(user_id)
        
        user_message = f"""❌ <b>To'lov rad etildi</b>

💰 Miqdor: {amount_uzs} UZS

Iltimos, agar bu xatolik bo'lsa, adminga murojaat qiling: {ADMIN_USERNAME}"""
        
        if user_lang == "ru":
            user_message = f"""❌ <b>Платеж отклонен</b>

💰 Сумма: {amount_uzs} UZS

Пожалуйста, свяжитесь с админом если эта ошибка: {ADMIN_USERNAME}"""
        elif user_lang == "en":
            user_message = f"""❌ <b>Payment Declined</b>

💰 Amount: {amount_uzs} UZS

Please contact admin if this is a mistake: {ADMIN_USERNAME}"""
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=user_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        
        # Get original payment request details
        payment_key = f"payment_{user_id}_{amount_uzs}"
        payment_info = context.bot_data.get(payment_key, {})
        
        # Get user info
        try:
            user = await context.bot.get_chat(user_id)
            user_name = user.first_name or f"User_{user_id}"
            username = user.username
        except:
            user_name = f"User_{user_id}"
            username = None
        
        # Format timestamps
        original_time = payment_info.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        decline_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update message for the admin who declined
        admin_update = (
            f"❌ <b>DECLINED</b> by @{query.from_user.username or query.from_user.first_name}\n"
            f"💳 <b>New Payment Request</b>\n"
            f"📅 Time: {original_time}\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"👤 Name: {user_name}\n"
        )
        if username:
            admin_update += f"👤 Username: @{username}\n"
        admin_update += (
            f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
            f"🏷️ Type: Standard\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {decline_time}"
        )
        
        await query.edit_message_text(
            admin_update,
            parse_mode=ParseMode.HTML
        )
        
        # Update ALL other admins' messages
        admin_messages = payment_info.get('messages', {})
        
        for admin_id, message_id in admin_messages.items():
            if str(admin_id) != str(query.from_user.id):
                try:
                    await context.bot.edit_message_text(
                        chat_id=admin_id,
                        message_id=message_id,
                        text=admin_update,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to update message for admin {admin_id}: {e}")
        
        # Clear stored message IDs
        if payment_key in context.bot_data:
            del context.bot_data[payment_key]
        
        await query.answer("❌ Payment declined", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error in decline_payment: {e}")
        await query.answer("❌ Error processing payment decline", show_alert=True)



async def contact_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin handler to get user contact link"""
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if str(query.from_user.id) != ADMIN_CHAT_ID:
        await query.answer("⛔ Access denied. Admin only.", show_alert=True)
        return
    
    try:
        # Parse callback data: contact_user_{user_id}
        parts = query.data.split("_")
        user_id = int(parts[2])
        
        # Get user info
        try:
            user = await context.bot.get_chat(user_id)
            if user.username:
                contact_link = f"https://t.me/{user.username}"
                message = f"👤 Contact user: @{user.username}\n🔗 {contact_link}"
            else:
                contact_link = f"tg://user?id={user_id}"
                message = f"👤 User ID: {user_id}\n🔗 {contact_link}\n\n⚠️ User has no username"
            
            await query.answer(message, show_alert=True)
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await query.answer(f"👤 User ID: {user_id}\n🔗 tg://user?id={user_id}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in contact_user: {e}")
        await query.answer("❌ Error getting user info", show_alert=True)


async def handle_topup_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show balance top-up menu - now includes Stars payment option"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    user_lang = await get_user_language(query.from_user.id)
    
    # Main payment method selection menu for manual mode
    menu_messages = {
        "uz": "💰 <b>To'lov usulini tanlang:</b>\n\n"
              "• <b>Karta orqali (UZCARD, HUMO, VISA)</b> - Admin tasdiqidan keyin\n"
              "• <b>Telegram Stars</b> - Telegramning ichki valyutasi orqali",
        "ru": "💰 <b>Выберите способ оплаты:</b>\n\n"
              "• <b>Через карту</b> - После подтверждения админа\n"
              "• <b>Telegram Stars</b> - Через внутреннюю валюту Telegram",
        "en": "💰 <b>Choose payment method:</b>\n\n"
              "• <b>Card Transfer (UZCARD, HUMO, VISA)</b> - After admin confirmation\n"
              "• <b>Telegram Stars</b> - Via Telegram's internal currency"
    }
    
    keyboard = [
        [
            InlineKeyboardButton(
                "💳 " + ("Karta orqali (UZCARD, HUMO, VISA)" if user_lang == "uz" else "Через карту (UZCARD, HUMO, VISA)" if user_lang == "ru" else "Card Transfer (UZCARD, HUMO, VISA)"),
                callback_data="manual_card_payment_menu"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐️ " + ("Telegram Stars orqali" if user_lang == "uz" else "Через Telegram Stars" if user_lang == "ru" else "Telegram Stars"),
                callback_data="stars_quiz_payment_menu"
            )
        ],
        [
            InlineKeyboardButton(
                TRANSLATIONS[user_lang].get("back", "« Back"),
                callback_data="balance"
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            menu_messages.get(user_lang, menu_messages["uz"]),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except:
        await query.message.reply_text(
            menu_messages.get(user_lang, menu_messages["uz"]),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )


async def show_manual_card_amounts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show card payment amount selection menu"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    user_lang = await get_user_language(query.from_user.id)
    
    # Menu message
    menu_messages = {
        "uz": "💳 <b>Karta orqali to'lash</b>\n\nKerakli miqdorni tanlang:\n\n Eslatib o'tamiz, 21 ta savolgacha bo'lgan quizlar - 3 000 UZS, \n30 savolgacha esa - 4 000 UZS. Shunga qarab kerakli miqdorni belgilang.",
        "ru": "💳 <b>Оплата картой</b>\n\nВыберите сумму: \n\nПомните, что викторины до 21 вопроса - 3 000 UZS, \nдо 30 вопросов - 4 000 UZS. Выберите нужную сумму.",
        "en": "💳 <b>Card Payment</b>\n\nSelect amount: \n\nRemember, quizzes up to 21 questions are 3,000 UZS, \nup to 30 questions are 4,000 UZS. Select the appropriate amount."
    }
    
    # Create keyboard with amount buttons
    keyboard = []
    amounts = ["1000", "2000","3000","4000","5000", "6000", "9000", "10000", "12000", "15000", "20000", "30000", "40000", "50000"]
    
    # Create 2 buttons per row
    for i in range(0, len(amounts), 2):
        row = []
        for j in range(2):
            if i + j < len(amounts):
                amount = amounts[i + j]
                row.append(InlineKeyboardButton(
                    f"💵 {amount} so'm",
                    callback_data=f"topup_{amount}"
                ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(
        TRANSLATIONS[user_lang].get("back", "« Back"),
        callback_data="topup_balance"
    )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            menu_messages.get(user_lang, menu_messages["uz"]),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except:
        await query.message.reply_text(
            menu_messages.get(user_lang, menu_messages["uz"]),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )


async def get_payment_mode(bot_id: str = BOT_ID) -> str:
    """Get current payment mode from database for specific bot"""
    try:
        response = supabase.table(TBL.ADMIN_SETTINGS).select("payment_mode").eq("bot_id", bot_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("payment_mode", "manual")
        else:
            # If no setting exists, create default one
            await set_payment_mode("manual", bot_id)
            return "manual"
    except Exception as e:
        logger.error(f"Error getting payment mode for {bot_id}: {e}")
        return "manual"  # Default to manual on error


async def set_payment_mode(mode: str, bot_id: str = BOT_ID, admin_id: int = None) -> bool:
    """Set payment mode in database for specific bot"""
    try:
        if mode not in ["auto", "manual"]:
            logger.error(f"Invalid payment mode: {mode}")
            return False
        
        # Check if record exists for this bot
        response = supabase.table(TBL.ADMIN_SETTINGS).select("*").eq("bot_id", bot_id).execute()
        
        timestamp = datetime.now().isoformat()
        
        if response.data and len(response.data) > 0:
            # Update existing record for this bot
            supabase.table(TBL.ADMIN_SETTINGS).update({
                "payment_mode": mode,
                "updated_at": timestamp,
                "admin_id": admin_id or int(ADMIN_CHAT_ID)
            }).eq("bot_id", bot_id).execute()
        else:
            # Insert new record for this bot
            supabase.table(TBL.ADMIN_SETTINGS).insert({
                "bot_id": bot_id,
                "payment_mode": mode,
                "admin_id": admin_id or int(ADMIN_CHAT_ID),
                "created_at": timestamp,
                "updated_at": timestamp
            }).execute()
        
        logger.info(f"Payment mode set to {mode} for bot {bot_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting payment mode for {bot_id}: {e}")
        return False


async def payment_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view/switch payment mode"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Access denied. Admin only.")
        return
    
    try:
        current_mode = await get_payment_mode(BOT_ID)
        
        bot_name = BOT_NAME
        
        message = f"""⚙️ <b>Payment Mode Settings</b>

🤖 Bot: <b>{bot_name}</b>
📊 Current Mode: <b>{current_mode.upper()}</b>

<b>Modes:</b>
🔵 <b>AUTO</b> - Automatic payment via Click/Payme
🟢 <b>MANUAL</b> - Manual payment with card transfer

Select mode:"""
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔵 Auto Payment" + (" ✅" if current_mode == "auto" else ""),
                    callback_data="set_payment_auto"
                ),
                InlineKeyboardButton(
                    "🟢 Manual Payment" + (" ✅" if current_mode == "manual" else ""),
                    callback_data="set_payment_manual"
                )
            ],
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_payment_mode")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in payment_mode_command: {e}")
        await update.message.reply_text(
            "❌ Error loading payment mode settings"
        )


async def handle_set_payment_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment mode change callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check if user is admin
    if str(user_id) != ADMIN_CHAT_ID:
        await query.answer("⛔ Access denied. Admin only.", show_alert=True)
        return
    
    try:
        bot_name = BOT_NAME
        
        if query.data == "set_payment_auto":
            new_mode = "auto"
            mode_name = "Auto Payment"
            emoji = "🔵"
        elif query.data == "set_payment_manual":
            new_mode = "manual"
            mode_name = "Manual Payment"
            emoji = "🟢"
        elif query.data == "refresh_payment_mode":
            # Just refresh the current status
            current_mode = await get_payment_mode(BOT_ID)
            message = f"""⚙️ <b>Payment Mode Settings</b>

🤖 Bot: <b>{bot_name}</b>
📊 Current Mode: <b>{current_mode.upper()}</b>

<b>Modes:</b>
🔵 <b>AUTO</b> - Automatic payment via Click/Payme
🟢 <b>MANUAL</b> - Manual payment with card transfer

Select mode:"""
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔵 Auto Payment" + (" ✅" if current_mode == "auto" else ""),
                        callback_data="set_payment_auto"
                    ),
                    InlineKeyboardButton(
                        "🟢 Manual Payment" + (" ✅" if current_mode == "manual" else ""),
                        callback_data="set_payment_manual"
                    )
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_payment_mode")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return
        else:
            return
        
        # Set the new payment mode for this specific bot
        success = await set_payment_mode(new_mode, BOT_ID, user_id)
        
        if success:
            message = f"""✅ <b>Payment Mode Updated</b>

🤖 Bot: <b>{bot_name}</b>
{emoji} New Mode: <b>{mode_name.upper()}</b>

<b>Modes:</b>
🔵 <b>AUTO</b> - Automatic payment via Click/Payme
🟢 <b>MANUAL</b> - Manual payment with card transfer

Select mode:"""
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔵 Auto Payment" + (" ✅" if new_mode == "auto" else ""),
                        callback_data="set_payment_auto"
                    ),
                    InlineKeyboardButton(
                        "🟢 Manual Payment" + (" ✅" if new_mode == "manual" else ""),
                        callback_data="set_payment_manual"
                    )
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_payment_mode")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            await query.answer(f"✅ Payment mode changed to {mode_name}", show_alert=True)
        else:
            await query.answer("❌ Failed to update payment mode", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in handle_set_payment_mode: {e}")
        await query.answer("❌ Error updating payment mode", show_alert=True)


def setup_manual_payment_handlers(application: Application) -> None:
    """Setup manual payment handlers"""
    
    # Admin payment mode command
    application.add_handler(CommandHandler("payment_mode", payment_mode_command))
    
    # Payment mode callback handlers
    application.add_handler(CallbackQueryHandler(
        handle_set_payment_mode, 
        pattern="^(set_payment_auto|set_payment_manual|refresh_payment_mode)$"
    ))
    
    # Balance top-up menu handler (main payment method selection)
    application.add_handler(CallbackQueryHandler(handle_topup_balance_menu, pattern="^topup_balance$"))
    
    # Card payment amounts menu handler
    application.add_handler(CallbackQueryHandler(show_manual_card_amounts_menu, pattern="^manual_card_payment_menu$"))
    
    # Amount selection handlers (standard amounts)
    application.add_handler(CallbackQueryHandler(
        handle_topup_amount_manual, 
        pattern="^topup_(1000|2000|3000|4000|5000|6000|9000|10000|12000|15000|20000|30000|40000|50000)$"
    ))
    

    # Admin payment approval handlers
    application.add_handler(CallbackQueryHandler(approve_payment, pattern="^approve_payment_"))
    application.add_handler(CallbackQueryHandler(decline_payment, pattern="^decline_payment_"))
    application.add_handler(CallbackQueryHandler(contact_user, pattern="^contact_user_"))
    application.add_handler(CommandHandler("send_check", send_check_command))

    
    # Payment status handlers
    application.add_handler(CallbackQueryHandler(payment_pending, pattern="^payment_pending$"))
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.Document.ALL | filters.TEXT) & 
        ~filters.COMMAND,
        handle_receipt_submission
    ), group=0) 
    
    logger.info("Manual payment handlers registered successfully")