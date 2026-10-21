from src.tables import TBL
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from src.user_management import get_user_language, run_supabase, get_account_snapshot

from src.imports import supabase, ADMIN_USERNAME

logger = logging.getLogger(__name__)

# Subscription pricing in UZS (kopecks stored in DB)
SUBSCRIPTION_PLANS = {
    "1_month": {
        "price_uzs": 30000,
        "price_kopecks": 3000000,
        "duration_days": 30,
        "duration_months": 1
    },
    "3_months": {
        "price_uzs": 50000,
        "price_kopecks": 5000000,
        "duration_days": 90,
        "duration_months": 3,
        "discount": "44% OFF"  # (90000 - 50000) / 90000
    },
    "6_months": {
        "price_uzs": 90000,
        "price_kopecks": 9000000,
        "duration_days": 180,
        "duration_months": 6,
        "discount": "60% OFF"  # (180000 - 90000) / 180000
    },
    "1_year": {
        "price_uzs": 150000,
        "price_kopecks": 15000000,
        "duration_days": 365,
        "duration_months": 12,
        "discount": "80% OFF"  # (360000 - 150000) / 360000
    }
}

PREMIUM_TRANSLATIONS = {
    "uz": {
        "subscribe_title": "🌟 <b>Premium Obuna</b>",
        "current_plan": "📊 <b>Joriy rejangiz:</b> {plan}",
        "valid_until": "⏰ Amal qilish muddati: {date}",
        "no_subscription": "❌ Sizda hozirda obuna yo'q",
        "features_title": "\n✨ <b>Premium imkoniyatlari:</b>",
        "feature_questions": "• 📝 50 gacha savol (40, 50 savol tanlash imkoniyati)",
        "feature_daily_free": "• 🎁 Har kuni 3 ta bepul quiz",
        "feature_priority": "• ⚡ Tezkor ishlov berish",
        "feature_support": "• 💎 Premium qo'llab-quvvatlash",
        "feature_no_ads": "• 🚫 Reklamasiz",
        "feature_advanced": "• 🎯 Kengaytirilgan quiz sozlamalari",
        "plans_title": "\n💰 <b>Obuna rejalari:</b>",
        "plan_1month": "📅 <b>1 oy</b> - <code>30,000</code> so'm",
        "plan_3months": "📅 <b>3 oy</b> - <s>90,000</s> <code>50,000</code> so'm <b>(44% chegirma!)</b>",
        "plan_6months": "📅 <b>6 oy</b> - <s>180,000</s> <code>90,000</code> so'm <b>(50% chegirma!)</b>",
        "plan_1year": "📅 <b>1 yil</b> - <s>360,000</s> <code>150,000</code> so'm <b>(58% chegirma!)</b>",
        "choose_plan": "\n👇 Rejani tanlang:",
        "btn_1month": "📅 1 oy - 30,000 so'm",
        "btn_3months": "🔥 3 oy - 50,000 so'm (44% OFF)",
        "btn_6months": "💎 6 oy - 90,000 so'm (60% OFF)",
        "btn_1year": "⭐ 1 yil - 150,000 so'm (80% OFF)",
        "btn_back": "« Orqaga",
        "payment_method_title": "💳 <b>To'lov usulini tanlang</b>\n\n📦 Obuna: <b>{plan}</b>\n💰 Narx: <b>{price} so'm</b>",
        "btn_card": "💳 Karta orqali",
        "btn_stars": "⭐ Telegram Stars",
        "manual_payment_msg": """💳 <b>Obuna sotib olish</b>

📦 Obuna: <b>{plan}</b>
💰 Narx: <b>{price} so'm</b>

📋 <b>To'lov qilish tartibi:</b>
1️⃣ Quyidagi karta raqamiga 30 daqiqa ichida {price} so'm o'tkazing:
   <code>{card_number}</code>

2️⃣ To'lov chekini admin {ADMIN_USERNAME} ga yuboring

3️⃣ Obuna admin tomonidan tasdiqlanganidan keyin faollashtiriladi

⚠️ <b>Muhim:</b> Chekni yuborishni unutmang!""",
        "btn_send_check": "💬 Chekni yuborish",
        "subscription_active": "✅ <b>Obuna faollashtirildi!</b>\n\n📦 Reja: <b>{plan}</b>\n⏰ Amal qilish muddati: <b>{end_date}</b>\n\nRahmat! 🎉",
        "daily_free_info": "\n🎁 <b>Bugungi bepul quizlar:</b> {used}/3 ishlatilgan",
        "free_quizzes_reset": "🔄 Bepul quizlar ertaga yangilanadi"
    },
    "ru": {
        "subscribe_title": "🌟 <b>Premium Подписка</b>",
        "current_plan": "📊 <b>Ваш текущий план:</b> {plan}",
        "valid_until": "⏰ Действует до: {date}",
        "no_subscription": "❌ У вас пока нет подписки",
        "features_title": "\n✨ <b>Возможности Premium:</b>",
        "feature_questions": "• 📝 До 50 вопросов (выбор 40, 50 вопросов)",
        "feature_daily_free": "• 🎁 3 бесплатных викторины каждый день",
        "feature_priority": "• ⚡ Приоритетная обработка",
        "feature_support": "• 💎 Premium поддержка",
        "feature_no_ads": "• 🚫 Без рекламы",
        "feature_advanced": "• 🎯 Расширенные настройки викторин",
        "plans_title": "\n💰 <b>Планы подписки:</b>",
        "plan_1month": "📅 <b>1 месяц</b> - <code>30,000</code> сум",
        "plan_3months": "📅 <b>3 месяца</b> - <s>90,000</s> <code>50,000</code> сум <b>(скидка 44%!)</b>",
        "plan_6months": "📅 <b>6 месяцев</b> - <s>180,000</s> <code>90,000</code> сум <b>(скидка 50%!)</b>",
        "plan_1year": "📅 <b>1 год</b> - <s>360,000</s> <code>150,000</code> сум <b>(скидка 58%!)</b>",
        "choose_plan": "\n👇 Выберите план:",
        "btn_1month": "📅 1 месяц - 30,000 сум",
        "btn_3months": "🔥 3 месяца - 50,000 сум (44% OFF)",
        "btn_6months": "💎 6 месяцев - 90,000 сум (60% OFF)",
        "btn_1year": "⭐ 1 год - 150,000 сум (80% OFF)",
        "btn_back": "« Назад",
        "payment_method_title": "💳 <b>Выберите способ оплаты</b>\n\n📦 Подписка: <b>{plan}</b>\n💰 Цена: <b>{price} сум</b>",
        "btn_card": "💳 Картой",
        "btn_stars": "⭐ Telegram Stars",
        "manual_payment_msg": """💳 <b>Купить подписку</b>

📦 Подписка: <b>{plan}</b>
💰 Цена: <b>{price} сум</b>

📋 <b>Порядок оплаты:</b>
1️⃣ Переведите {price} сум на карту в течение 30 минут:
   <code>{card_number}</code>

2️⃣ Отправьте чек оплаты админу {ADMIN_USERNAME}

3️⃣ Подписка будет активирована после подтверждения админа

⚠️ <b>Важно:</b> Не забудьте отправить чек!""",
        "btn_send_check": "💬 Отправить чек",
        "subscription_active": "✅ <b>Подписка активирована!</b>\n\n📦 План: <b>{plan}</b>\n⏰ Действует до: <b>{end_date}</b>\n\nСпасибо! 🎉",
        "daily_free_info": "\n🎁 <b>Бесплатные викторины сегодня:</b> {used}/3 использовано",
        "free_quizzes_reset": "🔄 Бесплатные викторины обновятся завтра"
    },
    "en": {
        "subscribe_title": "🌟 <b>Premium Subscription</b>",
        "current_plan": "📊 <b>Your current plan:</b> {plan}",
        "valid_until": "⏰ Valid until: {date}",
        "no_subscription": "❌ You don't have a subscription yet",
        "features_title": "\n✨ <b>Premium Features:</b>",
        "feature_questions": "• 📝 Up to 50 questions (40, 50 question options)",
        "feature_daily_free": "• 🎁 3 free quizzes daily",
        "feature_priority": "• ⚡ Priority processing",
        "feature_support": "• 💎 Premium support",
        "feature_no_ads": "• 🚫 Ad-free experience",
        "feature_advanced": "• 🎯 Advanced quiz settings",
        "plans_title": "\n💰 <b>Subscription Plans:</b>",
        "plan_1month": "📅 <b>1 month</b> - <code>30,000</code> UZS",
        "plan_3months": "📅 <b>3 months</b> - <s>90,000</s> <code>50,000</code> UZS <b>(44% OFF!)</b>",
        "plan_6months": "📅 <b>6 months</b> - <s>180,000</s> <code>90,000</code> UZS <b>(50% OFF!)</b>",
        "plan_1year": "📅 <b>1 year</b> - <s>360,000</s> <code>150,000</code> UZS <b>(58% OFF!)</b>",
        "choose_plan": "\n👇 Choose your plan:",
        "btn_1month": "📅 1 month - 30,000 UZS",
        "btn_3months": "🔥 3 months - 50,000 UZS (44% OFF)",
        "btn_6months": "💎 6 months - 90,000 UZS (60% OFF)",
        "btn_1year": "⭐ 1 year - 150,000 UZS (80% OFF)",
        "btn_back": "« Back",
        "payment_method_title": "💳 <b>Choose payment method</b>\n\n📦 Subscription: <b>{plan}</b>\n💰 Price: <b>{price} UZS</b>",
        "btn_card": "💳 Card Payment",
        "btn_stars": "⭐ Telegram Stars",
        "manual_payment_msg": """💳 <b>Buy Subscription</b>

📦 Subscription: <b>{plan}</b>
💰 Price: <b>{price} UZS</b>

📋 <b>Payment instructions:</b>
1️⃣ Transfer {price} UZS to the card within 30 minutes:
   <code>{card_number}</code>

2️⃣ Send payment receipt to admin {ADMIN_USERNAME}

3️⃣ Subscription will be activated after admin confirmation

⚠️ <b>Important:</b> Don't forget to send the receipt!""",
        "btn_send_check": "💬 Send Receipt",
        "subscription_active": "✅ <b>Subscription Activated!</b>\n\n📦 Plan: <b>{plan}</b>\n⏰ Valid until: <b>{end_date}</b>\n\nThank you! 🎉",
        "daily_free_info": "\n🎁 <b>Free quizzes today:</b> {used}/3 used",
        "free_quizzes_reset": "🔄 Free quizzes reset tomorrow"
    }
}







async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /subscribe command AND callback query"""
    user_id = update.effective_user.id
    user_lang = await get_user_language(user_id)
    t = PREMIUM_TRANSLATIONS[user_lang]
    
    row = await get_account_snapshot(user_id)
    subscription = parse_subscription(row)



    # Build message
    message = t["subscribe_title"] + "\n\n"
    
    if subscription and subscription["is_active"]:
        plan_name = get_plan_name(subscription["subscription_type"], user_lang)
        end_date = subscription["subscription_end"].strftime("%d.%m.%Y")
        message += t["current_plan"].format(plan=plan_name) + "\n"
        message += t["valid_until"].format(date=end_date)
        
        # Add daily free quizzes info if premium
        daily_info = parse_daily_free(row)
        message += t["daily_free_info"].format(used=daily_info["used"])
        if daily_info["used"] >= 3:
            message += "\n" + t["free_quizzes_reset"]
    else:
        message += t["no_subscription"] + "\n"
    
    # Add features
    message += "\n" + t["feature_questions"]
    message += "\n" + t["feature_daily_free"]
    message += "\n" + t["feature_support"]
    message += "\n" + t["feature_advanced"] + "\n"
    
    # Add plans
    message += t["plans_title"]
    message += "\n" + t["plan_1month"]
    message += "\n" + t["plan_3months"]
    message += "\n" + t["plan_6months"]
    message += "\n" + t["plan_1year"]
    
    message += t["choose_plan"]
    
    # Create keyboard
    keyboard = [
        [InlineKeyboardButton(t["btn_1month"], callback_data="subscribe_1_month")],
        [InlineKeyboardButton(t["btn_3months"], callback_data="subscribe_3_months")],
        [InlineKeyboardButton(t["btn_6months"], callback_data="subscribe_6_months")],
        [InlineKeyboardButton(t["btn_1year"], callback_data="subscribe_1_year")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ✅ FIX: Handle both message and callback_query
    if update.message:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

async def handle_subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subscription plan selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)
    t = PREMIUM_TRANSLATIONS[user_lang]
    
    # Extract plan from callback_data
    plan_key = query.data.replace("subscribe_", "")  # "1_month", "3_months", etc.
    
    if plan_key not in SUBSCRIPTION_PLANS:
        await query.answer("❌ Invalid plan", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS[plan_key]
    plan_name = get_plan_name(plan_key, user_lang)
    
    # Store selected plan in context
    context.user_data['selected_subscription_plan'] = plan_key
    
    # Show payment method selection
    message = t["payment_method_title"].format(
        plan=plan_name,
        price=f"{plan['price_uzs']:,}"
    )
    
    keyboard = [
        [InlineKeyboardButton(t["btn_card"], callback_data=f"sub_pay_card_{plan_key}")],
        [InlineKeyboardButton(t["btn_stars"], callback_data=f"sub_pay_stars_{plan_key}")],
        [InlineKeyboardButton(t["btn_back"], callback_data="back_to_subscribe")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )


async def handle_subscription_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle payment method selection for subscription"""
    from src.imports import CARD_NUMBER
    from handlers.manual_payment import send_payment_request_to_admin
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    username = query.from_user.username
    user_lang = await get_user_language(user_id)
    t = PREMIUM_TRANSLATIONS[user_lang]
    
    # Parse callback: sub_pay_card_1_month or sub_pay_stars_1_month
    parts = query.data.split("_")
    payment_method = parts[2]  # "card" or "stars"
    plan_key = "_".join(parts[3:])  # "1_month", "3_months", etc.
    
    if plan_key not in SUBSCRIPTION_PLANS:
        await query.answer("❌ Invalid plan", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS[plan_key]
    plan_name = get_plan_name(plan_key, user_lang)
    
    if payment_method == "card":
        # Manual card payment
        message = t["manual_payment_msg"].format(
            plan=plan_name,
            price=f"{plan['price_uzs']:,}",
            card_number=CARD_NUMBER,
            ADMIN_USERNAME=ADMIN_USERNAME
        )
        
        keyboard = [
            [InlineKeyboardButton(
                t["btn_send_check"],
                url=f"https://t.me/{ADMIN_USERNAME}"
            )],
            [InlineKeyboardButton(t["btn_back"], callback_data="back_to_subscribe")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        await send_payment_request_to_admin(
            context=context,
            user_id=user_id,
            user_name=user_name,
            amount_uzs=plan['price_uzs'],
            is_custom=False,
            username=username,
            is_subscription=True,           
            subscription_plan=plan_key    
        )
        
    elif payment_method == "stars":
        from telegram import LabeledPrice

        # Convert UZS price to Stars (same ~150 UZS/star ratio used elsewhere)
        stars_amount = max(1, round(plan['price_uzs'] / 150))

        payload = f"sub_stars_{user_id}_{plan_key}_{int(datetime.now(timezone.utc).timestamp())}"

        context.user_data['pending_stars_payment'] = {
            'is_subscription': True,
            'plan_key': plan_key,
            'stars': stars_amount,
            'uzs_amount': plan['price_uzs'],
            'payload': payload,
            'initiated_at': datetime.now(timezone.utc).isoformat()
        }

        title = {
            'uz': f"Obuna - {plan_name}",
            'ru': f"Подписка - {plan_name}",
            'en': f"Subscription - {plan_name}"
        }.get(user_lang, f"Subscription - {plan_name}")

        description = {
            'uz': f"{stars_amount} ⭐️ = {plan['price_uzs']:,} so'm ({plan_name})",
            'ru': f"{stars_amount} ⭐️ = {plan['price_uzs']:,} сум ({plan_name})",
            'en': f"{stars_amount} ⭐️ = {plan['price_uzs']:,} UZS ({plan_name})"
        }.get(user_lang, f"{stars_amount} Stars ({plan_name})")

    try:
        await context.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label="Stars", amount=stars_amount)],
            provider_token=""
        )

        info_msg = {
            'uz': "✅ To'lov havolasi yuborildi!\n\n⭐️ Telegram Stars orqali to'lang",
            'ru': "✅ Счет отправлен!\n\n⭐️ Оплатите через Telegram Stars",
            'en': "✅ Invoice sent!\n\n⭐️ Pay with Telegram Stars"
        }.get(user_lang, "✅ Invoice sent!")

        await query.edit_message_text(info_msg, parse_mode=ParseMode.HTML)

        # NEW: notify admin about the initiated Stars subscription request
        await notify_admin_stars_subscription_request(
            context=context,
            user_id=user_id,
            user_name=user_name,
            username=username,
            plan_name=plan_name,
            stars_amount=stars_amount,
            uzs_amount=plan['price_uzs']
        )
    except Exception as e:
        logger.error(f"Error sending subscription Stars invoice: {e}")
        await query.answer("❌ Failed to create Stars invoice. Try again.", show_alert=True)


async def notify_admin_stars_subscription_request(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    username: str,
    plan_name: str,
    stars_amount: int,
    uzs_amount: int
) -> None:
    """Notify admin(s) that a user initiated a Stars subscription payment."""
    from src.imports import NOTIFICATION_ADMIN_IDS
    from html import escape as escape_html

    if not NOTIFICATION_ADMIN_IDS:
        return

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        user_info = f"👤 User ID: <code>{user_id}</code>\n"
        user_info += f"👤 Name: {escape_html(user_name)}\n"
        if username:
            user_info += f"👤 Username: @{escape_html(username)}\n"

        message = (
            f"⭐️ <b>New Stars Payment Request (Subscription)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Time: {timestamp}\n"
            f"{user_info}"
            f"💰 Amount: <b>{uzs_amount:,} UZS</b>\n"
            f"⭐️ Stars: <b>{stars_amount}</b>\n"
            f"🏷️ Type: 🌟 Subscription ({plan_name})\n"
            f"📊 Status: <b>Waiting for payment...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        for admin_id in NOTIFICATION_ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about Stars subscription request: {e}")

        logger.info(f"Notified {len(NOTIFICATION_ADMIN_IDS)} admin(s) about Stars subscription request: user {user_id}")
    except Exception as e:
        logger.error(f"Failed to notify admins about Stars subscription request: {e}")



def get_plan_name(plan_key: str, language: str) -> str:
    """Get localized plan name"""
    plan_names = {
        "uz": {
            "1_month": "1 oylik",
            "3_months": "3 oylik",
            "6_months": "6 oylik",
            "1_year": "1 yillik"
        },
        "ru": {
            "1_month": "1 месяц",
            "3_months": "3 месяца",
            "6_months": "6 месяцев",
            "1_year": "1 год"
        },
        "en": {
            "1_month": "1 month",
            "3_months": "3 months",
            "6_months": "6 months",
            "1_year": "1 year"
        }
    }
    
    return plan_names.get(language, plan_names["en"]).get(plan_key, plan_key)


def _to_dt(value):
    if not value:
        return None
    if isinstance(value, str):
        if 'T' in value or ' ' in value:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(value, '%Y-%m-%d')
    else:
        dt = value
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_subscription(row: dict) -> dict:
    """Pure function: DB row -> subscription dict. No I/O."""
    if not row:
        return {"is_active": False}
    try:
        end_date = _to_dt(row.get('subscription_end'))
        start_date = _to_dt(row.get('subscription_start'))
    except Exception as e:
        logger.error(f"Bad subscription date: {e}")
        return {"is_active": False}
    if not end_date:
        return {"is_active": False}
    return {
        "is_active": end_date > datetime.now(timezone.utc),
        "subscription_type": row.get('subscription_type') or "premium",
        "subscription_start": start_date,
        "subscription_end": end_date,
    }


def parse_daily_free(row: dict) -> dict:
    """Pure function: DB row -> {'used', 'available', 'needs_reset'}."""
    sub = parse_subscription(row)
    if not sub.get("is_active"):
        return {"used": 0, "available": 0, "needs_reset": False}
    today = datetime.now(timezone.utc).date()
    last_reset = row.get('last_free_quiz_reset')
    needs_reset = False
    if last_reset:
        try:
            d = _to_dt(last_reset).date() if isinstance(last_reset, str) else last_reset
            needs_reset = d < today
        except Exception:
            needs_reset = True
    used = 0 if needs_reset else (row.get('daily_free_quizzes_used') or 0)
    return {"used": used, "available": max(0, 3 - used), "needs_reset": needs_reset}


async def get_user_subscription(user_id: int, row: dict = None) -> dict:
    try:
        if row is None:
            row = await get_account_snapshot(user_id)
        return parse_subscription(row)
    except Exception as e:
        logger.error(f"Error getting user subscription: {e}")
        return {"is_active": False}


async def get_daily_free_quizzes_info(user_id: int, row: dict = None) -> dict:
    try:
        if row is None:
            row = await get_account_snapshot(user_id)
        info = parse_daily_free(row)
        return {"used": info["used"], "available": info["available"]}
    except Exception as e:
        logger.error(f"Error getting daily free quizzes info: {e}")
        return {"used": 0, "available": 0}


async def use_daily_free_quiz(user_id: int, row: dict = None) -> bool:
    """Spend one free quiz. The .eq() on the old value stops two parallel taps spending the same one."""
    try:
        if row is None:
            row = await get_account_snapshot(user_id)
        info = parse_daily_free(row)
        if info["available"] <= 0:
            return False

        today = datetime.now(timezone.utc).date().isoformat()
        if info["needs_reset"]:
            q = lambda: supabase.table(TBL.USERS).update({
                'daily_free_quizzes_used': 1, 'last_free_quiz_reset': today
            }).eq('user_id', str(user_id)).execute()
        else:
            old = info["used"]
            q = lambda: supabase.table(TBL.USERS).update({
                'daily_free_quizzes_used': old + 1, 'last_free_quiz_reset': today
            }).eq('user_id', str(user_id)).eq('daily_free_quizzes_used', old).execute()

        r = await run_supabase(q)
        if not r.data:
            logger.warning(f"[FREE QUIZ] update matched 0 rows for {user_id} (parallel tap or missing user)")
            return False
        logger.info(f"[FREE QUIZ] user {user_id} used a free quiz")
        return True
    except Exception as e:
        logger.error(f"[FREE QUIZ] exception: {e}")
        return False


async def activate_subscription(user_id: int, plan_key: str, payment_method: str = "manual") -> bool:
    try:
        if plan_key not in SUBSCRIPTION_PLANS:
            logger.error(f"Invalid plan key: {plan_key}")
            return False
        plan = SUBSCRIPTION_PLANS[plan_key]
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=plan["duration_days"])

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS).update({
                'is_premium': True,
                'subscription_type': plan_key,
                'subscription_start': start_date.isoformat(),
                'subscription_end': end_date.isoformat(),
                'daily_free_quizzes_used': 0,
                'last_free_quiz_reset': start_date.date().isoformat()
            }).eq('user_id', str(user_id)).execute()
        )
        if not response.data:
            logger.error(f"[ACTIVATE] Update matched 0 rows for user_id={user_id}")
            return False

        await run_supabase(
            lambda: supabase.table(TBL.SUBSCRIPTION_HISTORY).insert({
                'user_id': user_id, 'subscription_type': plan_key,
                'amount': plan['price_kopecks'], 'payment_method': payment_method,
                'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(),
                'status': 'active'
            }).execute()
        )
        logger.info(f"[ACTIVATE] Activated {plan_key} for user {user_id}, until {end_date.isoformat()}")
        return True
    except Exception as e:
        logger.error(f"[ACTIVATE] Error activating subscription: {e}")
        return False


def setup_premium_handlers(application):
    """Setup premium/subscription handlers"""
    from telegram.ext import CommandHandler, CallbackQueryHandler
    
    # Command handler
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(
        handle_subscribe_callback,
        pattern="^subscribe_(1_month|3_months|6_months|1_year)$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_subscription_payment_method,
        pattern="^sub_pay_(card|stars)_"
    ))
    
    # ✅ ADD THIS: Handle "show_subscription_plans" callback from balance button
    application.add_handler(CallbackQueryHandler(
        subscribe_command,
        pattern="^show_subscription_plans$"
    ))
    
    logger.info("Premium/subscription handlers registered")