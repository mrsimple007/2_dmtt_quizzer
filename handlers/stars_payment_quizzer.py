import logging
from datetime import datetime
from html import escape as escape_html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from src.imports import NOTIFICATION_ADMIN_IDS

logger = logging.getLogger(__name__)

# Star payment amounts for quizzer
STAR_AMOUNTS = {
    "7_stars": {"stars": 7, "uzs": 1000},
    "13_stars": {"stars": 13, "uzs": 2000},
    "20_stars": {"stars": 20, "uzs": 3000},
    "33_stars": {"stars": 33, "uzs": 5000},
    "40_stars": {"stars": 40, "uzs": 6000},
    "47_stars": {"stars": 47, "uzs": 7000},
    "60_stars": {"stars": 60, "uzs": 9000},
    "80_stars": {"stars": 80, "uzs": 12000},
    "100_stars": {"stars": 100, "uzs": 15000},
    "133_stars": {"stars": 133, "uzs": 20000},
    "200_stars": {"stars": 200, "uzs": 30000},
    "267_stars": {"stars": 267, "uzs": 40000},
}

# Stars actually paid -> UZS to credit (so we never depend on context.user_data for top-ups)
STARS_TO_UZS = {data["stars"]: data["uzs"] for data in STAR_AMOUNTS.values()}

# Balance top-up payloads look like: stars_quiz_topup_<user_id>_<stars>_<timestamp>
TOPUP_PREFIX = "stars_quiz_topup_"

# Lightweight in-memory guard against duplicate updates.
# NOTE: resets on restart. For a real guarantee, add a UNIQUE constraint on
# transaction_id in your payments table.
_processed_charge_ids: set = set()


# ==================== Keyboard ====================
def build_stars_keyboard(user_lang: str) -> InlineKeyboardMarkup:
    """Build a compact 2-column keyboard from STAR_AMOUNTS.

    Label format: '⭐️ 100 - 15 000'
    """
    buttons = [
        InlineKeyboardButton(
            f"⭐️ {data['stars']} - {data['uzs'] // 1000} 000",
            callback_data=f"stars_quiz_pay_{key}",
        )
        for key, data in STAR_AMOUNTS.items()
    ]

    # 2 buttons per row
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    back_text = "Orqaga" if user_lang == "uz" else "Назад" if user_lang == "ru" else "Back"
    rows.append([InlineKeyboardButton(f"« {back_text}", callback_data="topup_balance")])

    return InlineKeyboardMarkup(rows)


async def show_stars_payment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Telegram Stars payment options for quizzer"""
    from src.user_management import get_user_language

    query = update.callback_query
    await query.answer()
    user_lang = await get_user_language(query.from_user.id)

    messages = {
        'uz': "⭐️ <b>Telegram Stars bilan to'ldirish</b>\n\n"
              "Kerakli miqdorni tanlang:\n"
              "<i>⭐️ Stars - so'm</i>",
        'ru': "⭐️ <b>Пополнение через Telegram Stars</b>\n\n"
              "Выберите сумму:\n"
              "<i>⭐️ Stars - сум</i>",
        'en': "⭐️ <b>Top-up with Telegram Stars</b>\n\n"
              "Select amount:\n"
              "<i>⭐️ Stars - UZS</i>",
    }

    text = messages.get(user_lang, messages['en'])
    reply_markup = build_stars_keyboard(user_lang)

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error editing message in stars menu: {e}")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


# ==================== Payment initiation ====================
async def handle_stars_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Telegram Stars payment initiation for quizzer (balance top-up)"""
    from src.user_management import get_user_language

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)

    amount_key = query.data.replace("stars_quiz_pay_", "")

    if amount_key not in STAR_AMOUNTS:
        await query.answer("Invalid amount", show_alert=True)
        return

    amount_data = STAR_AMOUNTS[amount_key]
    stars = amount_data["stars"]
    uzs_amount = amount_data["uzs"]

    title = {
        'uz': f"Balansni to'ldirish - {uzs_amount:,} so'm",
        'ru': f"Пополнение баланса - {uzs_amount:,} сум",
        'en': f"Balance Top-up - {uzs_amount:,} UZS",
    }.get(user_lang, f"Balance Top-up - {uzs_amount:,} UZS")

    description = {
        'uz': f"{stars} ⭐️ Telegram Stars = {uzs_amount:,} so'm",
        'ru': f"{stars} ⭐️ Telegram Stars = {uzs_amount:,} сум",
        'en': f"{stars} ⭐️ Telegram Stars = {uzs_amount:,} UZS",
    }.get(user_lang, f"{stars} ⭐️ Telegram Stars = {uzs_amount:,} UZS")

    payload = f"{TOPUP_PREFIX}{user_id}_{stars}_{int(datetime.now().timestamp())}"

    try:
        await context.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            currency="XTR",  # Telegram Stars currency code
            prices=[LabeledPrice(label="Stars", amount=stars)],
            provider_token="",  # Empty for Stars
        )

        await notify_admin_stars_payment_initiated(
            context=context,
            user_id=user_id,
            user_name=escape_html(query.from_user.full_name or "Unknown"),
            stars=stars,
            uzs_amount=uzs_amount,
        )

        info_msg = {
            'uz': "✅ To'lov havolasi yuborildi!\n\n⭐️ Telegram Stars orqali to'lang",
            'ru': "✅ Счет отправлен!\n\n⭐️ Оплатите через Telegram Stars",
            'en': "✅ Invoice sent!\n\n⭐️ Pay with Telegram Stars",
        }.get(user_lang, "✅ Invoice sent!\n\n⭐️ Pay with Telegram Stars")

        await query.edit_message_text(info_msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error sending Stars invoice: {e}")
        error_msg = {
            'uz': "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
            'ru': "❌ Произошла ошибка. Попробуйте снова.",
            'en': "❌ An error occurred. Please try again.",
        }.get(user_lang, "❌ An error occurred. Please try again.")

        await query.edit_message_text(error_msg)


def _parse_topup_payload(payload: str):
    """Parse 'stars_quiz_topup_<user_id>_<stars>_<ts>' -> (user_id, stars) or None."""
    if not payload or not payload.startswith(TOPUP_PREFIX):
        return None
    try:
        user_id, stars, _ts = payload[len(TOPUP_PREFIX):].split("_")
        return int(user_id), int(stars)
    except ValueError:
        return None


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Validate and answer pre-checkout query"""
    query = update.pre_checkout_query
    payload = query.invoice_payload or ""

    # Balance top-ups are validated strictly.
    # Other payloads (e.g. subscriptions from handlers.premium) are approved as before.
    if payload.startswith(TOPUP_PREFIX):
        parsed = _parse_topup_payload(payload)
        valid = (
            parsed is not None
            and parsed[0] == query.from_user.id
            and parsed[1] in STARS_TO_UZS
            and query.currency == "XTR"
            and query.total_amount == parsed[1]
        )
        if not valid:
            logger.warning(f"Pre-checkout rejected for user {query.from_user.id}: payload={payload}")
            await query.answer(ok=False, error_message="Invalid payment. Please try again.")
            return

    await query.answer(ok=True)
    logger.info(f"Pre-checkout approved for user {query.from_user.id}")


# ==================== Payment completion ====================
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful Stars payment - balance top-up OR subscription."""
    payment = update.message.successful_payment
    charge_id = payment.telegram_payment_charge_id

    if charge_id in _processed_charge_ids:
        logger.warning(f"Duplicate successful_payment ignored: {charge_id}")
        return

    payload = payment.invoice_payload or ""

    if payload.startswith(TOPUP_PREFIX):
        await _process_balance_topup(update, context)
    else:
        await _process_subscription(update, context)


async def _process_balance_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.user_management import (
        get_user_language,
        get_user_balance,
        update_user_balance,
        record_quiz_payment,
    )

    user_id = update.effective_user.id
    user_lang = await get_user_language(user_id)
    user_name = escape_html(update.effective_user.full_name or "Unknown")

    payment = update.message.successful_payment
    charge_id = payment.telegram_payment_charge_id

    # Trust what Telegram says was paid, not user_data
    stars_paid = payment.total_amount
    parsed = _parse_topup_payload(payment.invoice_payload)
    uzs_amount = STARS_TO_UZS.get(stars_paid)

    if uzs_amount is None or parsed is None or parsed[0] != user_id:
        logger.error(
            f"Unrecognized Stars top-up from {user_id}: stars={stars_paid}, "
            f"payload={payment.invoice_payload}, charge_id={charge_id}"
        )
        await notify_admin_stars_payment_failed(
            context, user_id, user_name, stars_paid, 0,
            f"Unrecognized payment. charge_id={charge_id}",
        )
        return

    try:
        # Balance is stored in kopecks (1 UZS = 100)
        amount_kopecks = uzs_amount * 100
        current_balance = await get_user_balance(user_id)
        if current_balance is None:
            current_balance = 0
        new_balance = current_balance + amount_kopecks

        balance_updated = await update_user_balance(user_id, new_balance)

        if not balance_updated:
            logger.error(f"Failed to update balance for user {user_id}")
            await notify_admin_stars_payment_failed(
                context, user_id, user_name, stars_paid, uzs_amount,
                f"Failed to update balance. charge_id={charge_id}",
            )
            return

        _processed_charge_ids.add(charge_id)

        # Recording the payment must not undo the credit if it fails.
        # TODO: verify these arguments match your record_quiz_payment signature.
        try:
            await record_quiz_payment(
                user_id=user_id,
                amount=amount_kopecks,
                payment_type="balance",
                payment_method="stars",
                transaction_id=charge_id,
                status="completed",
            )
        except Exception as e:
            logger.error(f"Balance credited but record_quiz_payment failed (charge_id={charge_id}): {e}")

        success_msg = {
            'uz': f"✅ <b>To'lov muvaffaqiyatli!</b>\n\n"
                  f"⭐️ To'langan: {stars_paid} Stars\n"
                  f"💰 Qo'shildi: {uzs_amount:,} so'm\n"
                  f"💳 Yangi balans: {new_balance // 100:,} so'm\n\n"
                  f"Rahmat! 🎉",
            'ru': f"✅ <b>Оплата успешна!</b>\n\n"
                  f"⭐️ Оплачено: {stars_paid} Stars\n"
                  f"💰 Добавлено: {uzs_amount:,} сум\n"
                  f"💳 Новый баланс: {new_balance // 100:,} сум\n\n"
                  f"Спасибо! 🎉",
            'en': f"✅ <b>Payment Successful!</b>\n\n"
                  f"⭐️ Paid: {stars_paid} Stars\n"
                  f"💰 Added: {uzs_amount:,} UZS\n"
                  f"💳 New balance: {new_balance // 100:,} UZS\n\n"
                  f"Thank you! 🎉",
        }.get(user_lang, "✅ Payment Successful!")

        await update.message.reply_text(success_msg, parse_mode=ParseMode.HTML)

        await notify_admin_stars_payment_success(
            context=context,
            user_id=user_id,
            user_name=user_name,
            stars_paid=stars_paid,
            uzs_amount=uzs_amount,
            new_balance=new_balance,
            charge_id=charge_id,
            old_balance=current_balance,
        )

        logger.info(f"Stars top-up successful for user {user_id}: {stars_paid} stars = {uzs_amount} UZS")

    except Exception as e:
        logger.error(f"Error processing Stars top-up: {e}")
        await notify_admin_stars_payment_failed(
            context, user_id, user_name, stars_paid, uzs_amount,
            f"{e} | charge_id={charge_id}",
        )


async def _process_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.user_management import get_user_language

    user_id = update.effective_user.id
    user_lang = await get_user_language(user_id)
    user_name = escape_html(update.effective_user.full_name or "Unknown")

    payment = update.message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    stars_paid = payment.total_amount

    payment_info = context.user_data.get('pending_stars_payment', {})

    if not payment_info or not payment_info.get('is_subscription'):
        logger.error(f"No pending subscription info for user {user_id}, charge_id={charge_id}")
        await notify_admin_stars_payment_failed(
            context, user_id, user_name, stars_paid, STARS_TO_UZS.get(stars_paid, 0),
            f"Payment received but no pending subscription info. charge_id={charge_id}",
        )
        return

    from handlers.premium import activate_subscription, get_plan_name, PREMIUM_TRANSLATIONS, get_user_subscription

    plan_key = payment_info['plan_key']
    uzs_amount = payment_info.get('uzs_amount', 0)

    try:
        success = await activate_subscription(user_id, plan_key, payment_method="stars")

        if success:
            _processed_charge_ids.add(charge_id)

            t = PREMIUM_TRANSLATIONS[user_lang]
            plan_name = get_plan_name(plan_key, user_lang)
            subscription = await get_user_subscription(user_id)
            end_date = (
                subscription["subscription_end"].strftime("%d.%m.%Y")
                if subscription.get("subscription_end") else "N/A"
            )

            await update.message.reply_text(
                t["subscription_active"].format(plan=plan_name, end_date=end_date),
                parse_mode=ParseMode.HTML,
            )

            await notify_admin_stars_payment_success(
                context=context,
                user_id=user_id,
                user_name=user_name,
                stars_paid=stars_paid,
                uzs_amount=uzs_amount,
                new_balance=0,
                charge_id=charge_id,
                old_balance=0,
            )
        else:
            logger.error(f"Failed to activate subscription for user {user_id}")
            await notify_admin_stars_payment_failed(
                context, user_id, user_name, stars_paid, uzs_amount,
                f"Failed to activate subscription. charge_id={charge_id}",
            )

    except Exception as e:
        logger.error(f"Error processing subscription Stars payment: {e}")
        await notify_admin_stars_payment_failed(
            context, user_id, user_name, stars_paid, uzs_amount,
            f"{e} | charge_id={charge_id}",
        )
    finally:
        context.user_data.pop('pending_stars_payment', None)


# ==================== Admin Notification Functions ====================
async def _send_to_admins(context: ContextTypes.DEFAULT_TYPE, message: str, label: str) -> None:
    if not NOTIFICATION_ADMIN_IDS:
        return

    for admin_id in NOTIFICATION_ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about Stars payment {label}: {e}")


async def notify_admin_stars_payment_initiated(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    stars: int,
    uzs_amount: int,
) -> None:
    """Notify admin(s) when user initiates Stars payment"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        f"🔔 <b>Stars Payment Initiated (Quizzer)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Time: {timestamp}\n"
        f"👤 User: {user_name}\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"⭐️ Stars: <b>{stars}</b>\n"
        f"💰 Amount: <b>{uzs_amount:,} UZS</b>\n"
        f"📊 Status: <b>Waiting for payment...</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await _send_to_admins(context, message, "initiation")


async def notify_admin_stars_payment_success(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    stars_paid: int,
    uzs_amount: int,
    new_balance: int,
    charge_id: str,
    old_balance: int,
) -> None:
    """Notify admin(s) about successful Stars payment"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    balance_increase = (new_balance - old_balance) // 100
    message = (
        f"✅ <b>Stars Payment Completed (Quizzer)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Time: {timestamp}\n"
        f"👤 User: {user_name}\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"⭐️ Stars Paid: <b>{stars_paid}</b>\n"
        f"💰 Amount: <b>{uzs_amount:,} UZS</b>\n"
        f"💵 Balance Increase: <b>+{balance_increase:,} UZS</b>\n"
        f"💳 Old Balance: {old_balance // 100:,} UZS\n"
        f"💳 New Balance: <b>{new_balance // 100:,} UZS</b>\n"
        f"🆔 Charge ID: <code>{charge_id}</code>\n"
        f"🔄 Method: <b>TELEGRAM STARS</b>\n"
        f"📊 Status: <b>✅ COMPLETED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await _send_to_admins(context, message, "success")


async def notify_admin_stars_payment_failed(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    user_name: str,
    stars_paid: int,
    uzs_amount: int,
    error: str,
) -> None:
    """Notify admin(s) about failed Stars payment processing"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        f"❌ <b>Stars Payment Processing Failed (Quizzer)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Time: {timestamp}\n"
        f"👤 User: {user_name}\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"⭐️ Stars: {stars_paid}\n"
        f"💰 Amount: {uzs_amount:,} UZS\n"
        f"🔴 Error: <code>{escape_html(str(error))}</code>\n"
        f"📊 Status: <b>❌ FAILED</b>\n"
        f"⚠️ <b>Action Required!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await _send_to_admins(context, message, "failure")


# ==================== Handler registration ====================
def setup_stars_payment_handlers(application: Application) -> None:
    """Setup Telegram Stars payment handlers for quizzer"""
    application.add_handler(CallbackQueryHandler(show_stars_payment_menu, pattern="^stars_quiz_payment_menu$"))
    application.add_handler(CallbackQueryHandler(handle_stars_payment, pattern="^stars_quiz_pay_"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    logger.info("Telegram Stars payment handlers registered for Simple Quizzer")