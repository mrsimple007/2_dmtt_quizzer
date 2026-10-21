from src.tables import TBL
import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum
import aiohttp
from src.user_management import run_supabase
from src.cache import cache_get, cache_set, cache_del
from src.async_utils import fire_and_forget
from src.perf_timing import track_handler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from telegram.constants import ParseMode
from supabase import create_client, Client
from src.prompts_summarize import TRANSLATIONS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class PaymentMode(Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# ==================== Configuration ====================
GLOBALPAY_BASE_URL = os.getenv("GLOBALPAY_BASE_URL", "")
GLOBALPAY_USERNAME = os.getenv("GLOBALPAY_USERNAME", "")
GLOBALPAY_PASSWORD = os.getenv("GLOBALPAY_PASSWORD", "")
SERVICE_ID = os.getenv("SERVICE_ID", "")
CALLBACK_URL = os.getenv("CALLBACK_URL", "https://t.me/simplequizzer_bot")

SUPABASE_URL = os.environ.get("QUIZ_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("QUIZ_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Payment checking interval (in seconds)
PAYMENT_CHECK_INTERVAL = 5
MAX_CHECK_ATTEMPTS = 180  # 15 minutes with 5-second intervals

# Conversation states
CUSTOM_BALANCE_AMOUNT = 1


async def init_payment_tables() -> None:
    """Initialize required database tables"""
    try:
        supabase.table(TBL.ADMIN_SETTINGS).select("*").limit(1).execute()
    except:
        logger.info("admin_settings table will be created on first write")
    
    try:
        supabase.table(TBL.PAYMENT_TOKENS).select("*").limit(1).execute()
    except:
        logger.info("payment_tokens table will be created on first write")


async def get_payment_mode() -> PaymentMode:
    from src.imports import ADMIN_CHAT_ID
    cached = cache_get(("payment_mode",))
    if cached:
        return cached
    try:
        r = await run_supabase(lambda: supabase.table(TBL.ADMIN_SETTINGS).select("payment_mode")
                               .eq("admin_id", ADMIN_CHAT_ID).execute())
        mode = PaymentMode(r.data[0].get("payment_mode", "AUTO")) if r.data else PaymentMode.AUTO
    except Exception as e:
        logger.error(f"Error getting payment mode: {e}")
        return PaymentMode.AUTO
    cache_set(("payment_mode",), mode, 60)
    return mode


async def set_payment_mode(mode: PaymentMode) -> bool:
    from src.imports import ADMIN_CHAT_ID
    try:
        await run_supabase(lambda: supabase.table(TBL.ADMIN_SETTINGS).upsert({
            "admin_id": ADMIN_CHAT_ID, "payment_mode": mode.value,
            "updated_at": datetime.now().isoformat()}).execute())
        cache_del(("payment_mode",))
        return True
    except Exception as e:
        logger.error(f"Error setting payment mode: {e}")
        return False


async def store_payment_token(user_id, service_token, amount_uzs, is_custom=False) -> bool:
    try:
        await run_supabase(lambda: supabase.table(TBL.PAYMENT_TOKENS).insert({
            "user_id": str(user_id), "service_token": service_token, "amount_uzs": amount_uzs,
            "is_custom": is_custom, "status": "PENDING", "check_count": 0,
            "created_at": datetime.now().isoformat()}).execute())
        return True
    except Exception as e:
        logger.error(f"Error storing payment token: {e}")
        return False


async def get_payment_token(service_token: str):
    try:
        r = await run_supabase(lambda: supabase.table(TBL.PAYMENT_TOKENS).select("*")
                               .eq("service_token", service_token).execute())
        return r.data[0] if r.data else None
    except Exception as e:
        logger.error(f"Error getting payment token: {e}")
        return None


async def update_payment_status(service_token, status, globalpay_response=None) -> bool:
    try:
        data = {"status": status, "updated_at": datetime.now().isoformat()}
        if globalpay_response:
            data["response_data"] = json.dumps(globalpay_response)
        await run_supabase(lambda: supabase.table(TBL.PAYMENT_TOKENS).update(data)
                           .eq("service_token", service_token).execute())
        return True
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        return False


async def set_check_count(service_token: str, count: int) -> None:
    try:
        await run_supabase(lambda: supabase.table(TBL.PAYMENT_TOKENS).update({"check_count": count})
                           .eq("service_token", service_token).execute())
    except Exception as e:
        logger.error(f"Error setting check count: {e}")

async def increment_check_count(service_token: str) -> bool:
    """Increment check attempt count"""
    try:
        token_data = await get_payment_token(service_token)
        if not token_data:
            return False
        
        new_count = token_data.get("check_count", 0) + 1
        await run_supabase(lambda: supabase.table(TBL.PAYMENT_TOKENS).update({
            "check_count": new_count
        }).eq("service_token", service_token).execute())
        return True
    except Exception as e:
        logger.error(f"Error incrementing check count: {e}")
        return False


# ==================== GlobalPay API Integration ====================
class GlobalPayClient:
    def __init__(self):
        self.base_url = GLOBALPAY_BASE_URL
        self.username = GLOBALPAY_USERNAME
        self.password = GLOBALPAY_PASSWORD
        self.service_id = SERVICE_ID
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
    
    async def authenticate(self) -> bool:
        """Get merchant authentication token"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/v1/merchant/auth"
                
                payload = {
                    "username": self.username,
                    "password": self.password
                }
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                logger.info(f"Attempting auth with URL: {url}")
                
                async with session.post(url, json=payload, headers=headers) as response:
                    response_text = await response.text()
                    
                    logger.info(f"Auth response status: {response.status}")
                    
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                            self.access_token = data.get("access_token")
                            expires_in = data.get("expires_in", 3600)
                            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                            logger.info("Successfully authenticated with GlobalPay")
                            return True
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse auth response: {response_text}")
                            return False
                    else:
                        logger.error(f"Authentication failed: {response.status} - {response_text}")
                        return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _ensure_auth(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            return await self.authenticate()
        return True
    
    async def create_payment_token(
        self,
        user_id: int,
        amount_uzs: int,
        description: str,
        external_id: str
    ) -> Optional[Dict]:
        """Create a payment token"""
        if not await self._ensure_auth():
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/v1/user-service-tokens"
                
                logger.info(f"Creating payment token at URL: {url}")
                
                # Convert UZS to tiyins (1 UZS = 100 tiyins)
                amount_tiyins = amount_uzs * 100
                
                # Generate unique name and externalId (UUID)
                import uuid
                unique_id = str(uuid.uuid4())
                
                payload = {
                    "name": unique_id,
                    "description": description[:255],
                    "externalId": unique_id,
                    "account": str(user_id),
                    "externalServiceId": int(self.service_id),
                    "tokenLifespan": 1000,
                    "requestFields": [
                        {
                            "value": str(amount_tiyins),
                            "name": "amount"
                        },
                        {
                            "value": "UZS",
                            "name": "currency"
                        }
                    ],
                    "successRedirectUrl": CALLBACK_URL,
                    "failRedirectUrl": ""
                }
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                logger.info(f"Creating payment token with payload: {json.dumps(payload, indent=2)}")
                
                async with session.post(url, json=payload, headers=headers) as response:
                    response_text = await response.text()
                    logger.info(f"Payment token response status: {response.status}")
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        logger.info(f"Payment token created for user {user_id}")
                        return data
                    else:
                        logger.error(f"Failed to create payment token: {response_text}")
                        return None
        except Exception as e:
            logger.error(f"Error creating payment token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def check_payment_status(self, service_token: str) -> Optional[Dict]:
        """Check payment status using service token"""
        if not await self._ensure_auth():
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/v1/user-service-tokens/{service_token}"
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }
                
                logger.info(f"Checking payment status at: {url}")
                
                async with session.get(url, headers=headers) as response:
                    response_text = await response.text()
                    logger.info(f"Payment status response: {response.status}")
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        logger.info(f"Payment status data: {json.dumps(data, indent=2)}")
                        logger.info(f"Status: {data.get('status')}")
                        logger.info(f"Error field: {data.get('error')}")
                        logger.info(f"Error description: {data.get('errorDescription')}")
                        return data
                    else:
                        logger.warning(f"Payment status check returned {response.status}: {response_text}")
                        return None
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

def get_quiz_price(num_questions: int) -> int:
    """Return price in kopecks for the given number of questions."""
    if num_questions <= 20:
        return 300000  # 3000 UZS in kopecks
    elif num_questions <= 30:
        return 400000  # 4000 UZS in kopecks
    else:
        return 400000  # 4000 UZS in kopecks


# ==================== Payment Processing ====================
globalpay_client = GlobalPayClient()


async def initiate_payment_checkout(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    amount_uzs: int,
    description: str,
    is_custom: bool = False
) -> Optional[str]:
    """Initiate payment through GlobalPay and get checkout URL"""
    try:
        external_id = f"user_{user_id}_{int(datetime.now().timestamp())}"
        
        token_data = await globalpay_client.create_payment_token(
            user_id=user_id,
            amount_uzs=amount_uzs,
            description=description,
            external_id=external_id
        )
        
        if not token_data:
            logger.error(f"Failed to create payment token for user {user_id}")
            return None
        
        service_token = token_data.get("id")
        user_redirect_url = token_data.get("userRedirectUrl")
        
        # Store token in database
        await store_payment_token(user_id, service_token, amount_uzs, is_custom)
        
        # Start background task to check payment status
        asyncio.create_task(
            check_payment_status_loop(
                context=context,
                user_id=user_id,
                service_token=service_token,
                amount_uzs=amount_uzs
            )
        )
        
        logger.info(f"Payment checkout initiated for user {user_id}, token: {service_token}")
        return user_redirect_url
    
    except Exception as e:
        logger.error(f"Error initiating payment checkout: {e}")
        return None


async def check_payment_status_loop(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    service_token: str,
    amount_uzs: int
) -> None:
    """Background task to check payment status periodically"""
    check_count = 0
    
    while check_count < MAX_CHECK_ATTEMPTS:
        try:
            await asyncio.sleep(PAYMENT_CHECK_INTERVAL)
            check_count += 1
            if check_count % 12 == 0:                      # once a minute instead of every 5 s
                fire_and_forget(set_check_count(service_token, check_count))
            
            payment_status = await globalpay_client.check_payment_status(service_token)
            
            if not payment_status:
                continue
            
            status = payment_status.get("status")
            
            if status == "APPROVED":
                await handle_payment_approved(
                    context=context,
                    user_id=user_id,
                    service_token=service_token,
                    amount_uzs=amount_uzs,
                    payment_data=payment_status
                )
                break
            
            elif status == "FAILED":
                error = payment_status.get("error", "UNKNOWN_ERROR")
                await handle_payment_failed(
                    context=context,
                    user_id=user_id,
                    service_token=service_token,
                    amount_uzs=amount_uzs,
                    error=error,
                    payment_data=payment_status
                )
                break
        
        except Exception as e:
            logger.error(f"Error in payment check loop: {e}")
            continue
    
    # Payment check timed out
    if check_count >= MAX_CHECK_ATTEMPTS:
        await update_payment_status(service_token, "EXPIRED")
        await notify_payment_expired(context, user_id, service_token, amount_uzs)


async def handle_payment_approved(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    service_token: str,
    amount_uzs: int,
    payment_data: Dict
) -> None:
    try:
        from src.user_management import get_user_language
        
        # Update payment status in database
        await update_payment_status(service_token, "APPROVED", payment_data)
        
        amount_kopecks = amount_uzs * 100
        
        success = await add_balance(user_id, amount_kopecks, payment_type="balance_topup", payment_method="manual")
        
        if success:
            # Notify user
            user_lang = await get_user_language(user_id)
            user_message = format_payment_approved_message(user_lang, amount_uzs)
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
            
            # Get user name for admin notification
            try:
                user = await context.bot.get_chat(user_id)
                user_name = user.first_name or "Unknown"
                if user.last_name:
                    user_name += f" {user.last_name}"
                user_username = user.username
            except Exception as e:
                logger.error(f"Failed to get user name: {e}")
                user_name = "Unknown User"
                user_username = None
            
            # Notify admin
            await notify_admin_payment_success(
                context=context,
                user_name=user_name,
                user_id=user_id,
                user_username=user_username,
                amount_uzs=amount_uzs,
                payment_data=payment_data,
                mode="AUTO" if await get_payment_mode() == PaymentMode.AUTO else "MANUAL"
            )
        
        logger.info(f"Payment approved for user {user_id}, amount: {amount_uzs} UZS")
    
    except Exception as e:
        logger.error(f"Error handling payment approval: {e}")


async def handle_payment_failed(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    service_token: str,
    amount_uzs: int,
    error: str,
    payment_data: Dict
) -> None:
    """Handle failed payment"""
    try:
        from src.user_management import get_user_language
        
        # Update payment status in database
        await update_payment_status(service_token, "FAILED", payment_data)
        
        # Notify user
        user_lang = await get_user_language(user_id)
        user_message = format_payment_failed_message(user_lang, amount_uzs, error)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=user_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        
        # Notify admin
        await notify_admin_payment_failed(
            context=context,
            user_id=user_id,
            amount_uzs=amount_uzs,
            error=error
        )
        
        logger.warning(f"Payment failed for user {user_id}, error: {error}")
    
    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")


async def notify_payment_expired(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    service_token: str,
    amount_uzs: int
) -> None:
    """Notify when payment check times out"""
    try:
        from src.user_management import get_user_language
        
        user_lang = await get_user_language(user_id)
        
        if user_lang == "uz":
            message = (
                "⏰ <b>To'lov jarayoni vaqti o'tdi</b>\n\n"
                f"💰 Miqdor: {amount_uzs} UZS\n"
                "Iltimos qayta urinib ko'ring yoki adminga murojaat qiling."
            )
        elif user_lang == "ru":
            message = (
                "⏰ <b>Время платежа истекло</b>\n\n"
                f"💰 Сумма: {amount_uzs} UZS\n"
                "Пожалуйста, попробуйте снова или свяжитесь с администратором."
            )
        else:
            message = (
                "⏰ <b>Payment timeout</b>\n\n"
                f"💰 Amount: {amount_uzs} UZS\n"
                "Please try again or contact admin."
            )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error notifying payment expiration: {e}")


# ==================== Message Formatting ====================
def format_payment_approved_message(lang: str, amount_uzs: int) -> str:
    """Format payment approved message"""
    if lang == "uz":
        return (
            f"✅ <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n\n"
            f"💰 Miqdor: <b>{amount_uzs} UZS</b>\n"
            f"Balans o'z vaqtida to'ldirildi.\n\n"
            f"Rahmat! 🎉"
        )
    elif lang == "ru":
        return (
            f"✅ <b>Платеж успешно получен!</b>\n\n"
            f"💰 Сумма: <b>{amount_uzs} UZS</b>\n"
            f"Баланс пополнен.\n\n"
            f"Спасибо! 🎉"
        )
    else:
        return (
            f"✅ <b>Payment Successful!</b>\n\n"
            f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
            f"Balance updated.\n\n"
            f"Thank you! 🎉"
        )


def format_payment_failed_message(lang: str, amount_uzs: int, error: str) -> str:
    """Format payment failed message"""
    error_translation = {
        "INSUFFICIENT_FUNDS": {"uz": "Mablag' yetarli emas", "ru": "Недостаточно средств", "en": "Insufficient funds"},
        "CARD_ERROR": {"uz": "Karta xatosi", "ru": "Ошибка карты", "en": "Card error"},
        "PAYMENT_EXPIRED": {"uz": "To'lov vaqti tugadi", "ru": "Платеж истек", "en": "Payment expired"}
    }
    
    error_text = error_translation.get(error, {}).get(lang, error)
    
    if lang == "uz":
        return (
            f"❌ <b>To'lov amalga oshmadi</b>\n\n"
            f"💰 Miqdor: {amount_uzs} UZS\n"
            f"🔴 Sabab: {error_text}\n\n"
            f"Qayta urinib ko'ring."
        )
    elif lang == "ru":
        return (
            f"❌ <b>Платеж не прошел</b>\n\n"
            f"💰 Сумма: {amount_uzs} UZS\n"
            f"🔴 Причина: {error_text}\n\n"
            f"Попробуйте снова."
        )
    else:
        return (
            f"❌ <b>Payment Failed</b>\n\n"
            f"💰 Amount: {amount_uzs} UZS\n"
            f"🔴 Reason: {error_text}\n\n"
            f"Please try again."
        )


# ==================== Admin Notification ====================
async def notify_admin_payment_success(
    context: ContextTypes.DEFAULT_TYPE,
    user_name: str,
    user_id: int,
    user_username: str,
    amount_uzs: int,
    payment_data: Dict,
    mode: str = "AUTO"
) -> None:
    """Notify admin about successful payment"""
    try:
        from src.imports import ADMIN_CHAT_ID
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction_id = payment_data.get("externalId", "N/A")
        username_display = f"@{user_username}" if user_username else "No username"
        
        message = (
            f"✅ <b>Payment Approved</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Time: {timestamp}\n"
            f"👤 User name: {user_name}\n"
            f"👤 Username: {username_display}\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💰 Amount: <b>{amount_uzs} UZS</b>\n"
            f"🆔 Transaction ID: <code>{transaction_id}</code>\n"
            f"🔄 Mode: <b>{mode}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about payment success: {e}")


async def notify_admin_payment_failed(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    amount_uzs: int,
    error: str
) -> None:
    """Notify admin about failed payment"""
    try:
        from src.imports import ADMIN_CHAT_ID
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = (
            f"❌ <b>Payment Failed</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Time: {timestamp}\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💰 Amount: {amount_uzs} UZS\n"
            f"🔴 Error: {error}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about payment failure: {e}")

async def add_balance(user_id: int, amount: int, payment_type: str = "balance_topup", payment_method: str = "manual") -> bool:
    from src.user_management import get_user_balance, record_quiz_payment, update_user_balance
    """Add balance and record payment (except for referral bonuses)."""
    try:
        current_balance = await get_user_balance(user_id)
        if current_balance is None:
            current_balance = 0
        new_balance = current_balance + amount
        await update_user_balance(user_id, new_balance)
        
        # Only record payment if it's not a referral bonus
        if payment_type != "referral_bonus":
            await record_quiz_payment(
                user_id=user_id,
                amount=amount,
                payment_type=payment_type,
                payment_method=payment_method,
                status="completed"
            )
            logger.info(f"Added {amount} to user {user_id}. New balance: {new_balance}. Type: {payment_type} (recorded)")
        else:
            logger.info(f"Added {amount} to user {user_id}. New balance: {new_balance}. Type: referral_bonus (not recorded)")
        
        return True
    except Exception as e:
        logger.error(f"Error adding balance for user {user_id}: {e}")
        return False
    

async def deduct_balance(user_id: int, amount: int) -> bool:
    from src.imports import is_free_user
    if is_free_user(user_id):
        return True          # free user: nothing to deduct
    from src.user_management import get_user_balance, update_user_balance
    try:
        current_balance = await get_user_balance(user_id)
        if current_balance < amount:
            logger.warning(f"User {user_id} has insufficient balance for deduction.")
            return False
        new_balance = current_balance - amount
        await update_user_balance(user_id, new_balance)
        logger.info(f"Deducted {amount} from user {user_id}. New balance: {new_balance}")
        return True
    except Exception as e:
        logger.error(f"Error deducting balance for user {user_id}: {e}")
        return False

@track_handler("balance")
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.user_management import (get_user_language, get_account_snapshot,
                                     get_invited_users_count_cached)
    from handlers.premium import get_user_subscription, get_plan_name

    if update.callback_query:
        fire_and_forget(update.callback_query.answer())      # was awaited AFTER all the DB calls

    user_id = update.effective_user.id
    user_lang, snap, invited_count, subscription = await asyncio.gather(
        get_user_language(user_id), get_account_snapshot(user_id),
        get_invited_users_count_cached(user_id), get_user_subscription(user_id),
        return_exceptions=True,
    )
    if isinstance(user_lang, Exception):
        user_lang = "en"
    if isinstance(snap, Exception):
        snap = {}
    if isinstance(invited_count, Exception):
        invited_count = 0
    if isinstance(subscription, Exception):
        subscription = {"is_active": False}

    balance_uzs = (snap.get("balance") or 0) / 100
    balance_info = TRANSLATIONS[user_lang]["balance_info"].format(
        balance=int(balance_uzs),
        presentations_possible=int(balance_uzs // 3000),
        invited_count=invited_count,
    )

    if subscription.get("is_active"):
        plan_name = get_plan_name(subscription["subscription_type"], user_lang)
        end_date = subscription["subscription_end"].strftime("%d.%m.%Y")
        balance_info += {
            'uz': f"\n\n🌟 <b>Premium Obuna:</b> {plan_name}\n⏰ Amal qilish muddati: {end_date}",
            'ru': f"\n\n🌟 <b>Premium Подписка:</b> {plan_name}\n⏰ Действует до: {end_date}",
            'en': f"\n\n🌟 <b>Premium Subscription:</b> {plan_name}\n⏰ Valid until: {end_date}",
        }.get(user_lang, "")

    subscribe_text = {'uz': "🌟 Obuna sotib olish", 'ru': "🌟 Купить подписку",
                      'en': "🌟 Buy Subscription"}.get(user_lang, "🌟 Buy Subscription")
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(TRANSLATIONS[user_lang]["topup_button"], callback_data="topup_balance")],
        [InlineKeyboardButton(subscribe_text, callback_data="show_subscription_plans")],
        [InlineKeyboardButton(TRANSLATIONS[user_lang]["share_earn"], callback_data="share")],
    ])

    if update.message:
        await update.message.reply_text(balance_info, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                balance_info, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(
                balance_info, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def admin_add_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: /add <user_id> <amount_uzs>
    Manually records a payment (e.g. when a user sends the check directly to admin)."""
    from src.imports import ADMIN_CHAT_ID, NOTIFICATION_ADMIN_IDS
    from src.user_management import get_user_language, get_user_balance

    admin_user_id = update.effective_user.id
    if str(admin_user_id) != str(ADMIN_CHAT_ID) and admin_user_id not in NOTIFICATION_ADMIN_IDS:
        await update.message.reply_text("⛔ Access denied. Admin only.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /add <user_id> <amount_in_uzs>\n"
            "Example: /add 8437026582 1673000"
        )
        return

    try:
        target_user_id = int(args[0])
        amount_uzs = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments. user_id and amount must be numbers.")
        return

    if amount_uzs <= 0:
        await update.message.reply_text("❌ Amount must be positive.")
        return

    amount_kopecks = amount_uzs * 100

    success = await add_balance(
        target_user_id,
        amount_kopecks,
        payment_type="balance_topup",
        payment_method="manual"
    )

    if not success:
        await update.message.reply_text(f"❌ Failed to add balance for user {target_user_id}.")
        return

    new_balance = await get_user_balance(target_user_id) or 0

    await update.message.reply_text(
        f"✅ <b>Payment added</b>\n\n"
        f"👤 User ID: <code>{target_user_id}</code>\n"
        f"💰 Amount: <b>{amount_uzs:,} UZS</b>\n"
        f"💳 New balance: <b>{new_balance // 100:,} UZS</b>",
        parse_mode=ParseMode.HTML
    )

    # Notify the user their balance was topped up
    try:
        user_lang = await get_user_language(target_user_id) or 'uz'
        user_message = format_payment_approved_message(user_lang, amount_uzs)
        await context.bot.send_message(
            chat_id=target_user_id,
            text=user_message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to notify user {target_user_id} about manual payment: {e}")


async def topup_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show balance top-up options - includes Stars payment option."""
    from src.user_management import get_user_language
    from handlers.manual_payment import get_payment_mode as get_manual_payment_mode, handle_topup_balance_menu
    
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)
    
    # Check payment mode and route accordingly
    payment_mode = await get_manual_payment_mode()
    
    if payment_mode == "manual":
        # Route to manual payment handler
        await handle_topup_balance_menu(update, context)
        return
    
    # Main payment method selection menu
    keyboard = [
        [
            InlineKeyboardButton(
                "💳 " + ("Click orqali to'lash" if user_lang == "uz" else "Оплата через Click" if user_lang == "ru" else "Pay with Click"),
                callback_data="globalpay_payment_menu"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐️ " + ("Telegram Stars orqali to'lash" if user_lang == "uz" else "Оплата через Telegram Stars" if user_lang == "ru" else "Pay with Telegram Stars"),
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
    
    message_text = {
        'uz': "💰 <b>To'lov usulini tanlang:</b>\n\n"
              "• <b>Click</b> - UzCard, Humo kartalari orqali\n"
              "• <b>Telegram Stars</b> - Telegramning ichki valyutasi orqali",
        'ru': "💰 <b>Выберите способ оплаты:</b>\n\n"
              "• <b>Click</b> - через карты UzCard, Humo\n"
              "• <b>Telegram Stars</b> - через внутреннюю валюту Telegram",
        'en': "💰 <b>Choose payment method:</b>\n\n"
              "• <b>Click</b> - via UzCard, Humo cards\n"
              "• <b>Telegram Stars</b> - via Telegram's internal currency"
    }.get(user_lang, "💰 <b>Choose payment method:</b>")
    
    try:
        await query.edit_message_text(
            message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except:
        await query.message.reply_text(
            message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )


async def show_globalpay_amounts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show GlobalPay/Click payment amount selection."""
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("3,000 UZS", callback_data="globalpay_topup_3000"),
            InlineKeyboardButton("6,000 UZS", callback_data="globalpay_topup_6000")
        ],
        [
            InlineKeyboardButton("9,000 UZS", callback_data="globalpay_topup_9000"),
            InlineKeyboardButton("12,000 UZS", callback_data="globalpay_topup_12000")
        ],
        [
            InlineKeyboardButton("15,000 UZS", callback_data="globalpay_topup_15000")
        ],
        [
            InlineKeyboardButton(
                TRANSLATIONS[user_lang].get("back", "« Back"),
                callback_data="topup_balance"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            TRANSLATIONS[user_lang].get("select_topup_amount", "Select top-up amount:"),
            reply_markup=reply_markup
        )
    except:
        await query.message.reply_text(
            TRANSLATIONS[user_lang].get("select_topup_amount", "Select top-up amount:"),
            reply_markup=reply_markup
        )
        
async def handle_globalpay_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.manual_payment import BALANCE_AMOUNTS
    from src.user_management import get_user_language
    
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_lang = await get_user_language(user_id)
    
    # Extract amount from callback data
    callback_data = query.data
    amount_key = callback_data.replace("globalpay_topup_", "")
    amount_uzs = BALANCE_AMOUNTS.get(amount_key)
    
    if not amount_uzs:
        await query.message.reply_text("Invalid amount selected.")
        return
    
    # Show processing message
    processing_msg = TRANSLATIONS[user_lang].get(
        "processing_payment", 
        "⏳ Processing your payment..."
    )
    await query.edit_message_text(processing_msg)
    
    # Initiate payment checkout
    description = f"Balance top-up: {amount_uzs} UZS"
    checkout_url = await initiate_payment_checkout(
        context=context,
        user_id=user_id,
        amount_uzs=amount_uzs,
        description=description,
        is_custom=False
    )
    
    if checkout_url:
        keyboard = [[InlineKeyboardButton("💳 Pay Now", url=checkout_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        payment_msg = TRANSLATIONS[user_lang].get(
            "payment_initiated",
            f"💰 Payment initiated for {amount_uzs} UZS\n\n"
            "Click the button below to complete payment:"
        )
        
        await query.message.reply_text(
            payment_msg.format(amount=amount_uzs) if "{amount}" in payment_msg else payment_msg,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        error_msg = TRANSLATIONS[user_lang].get(
            "payment_error",
            "❌ Failed to initiate payment. Please try again later."
        )
        await query.message.reply_text(error_msg)


# ==================== Admin Handlers ====================
async def admin_payment_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to manage payment settings."""
    user_id = update.effective_user.id
    from src.imports import ADMIN_CHAT_ID
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Access denied. Admin only.")
        return
    
    current_mode = await get_payment_mode()
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅' if current_mode == PaymentMode.AUTO else '⚪'} Auto Verification",
                callback_data="admin_set_payment_auto"
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if current_mode == PaymentMode.MANUAL else '⚪'} Manual Verification",
                callback_data="admin_set_payment_manual"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"⚙️ <b>Payment Settings</b>\n\n"
        f"Current mode: <b>{current_mode.value}</b>\n\n"
        f"<b>Auto:</b> Payments verified automatically via GlobalPay API\n"
        f"<b>Manual:</b> Admin manually confirms payments"
    )
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def refund_quiz_payment(user_id: int, amount: int) -> bool:
    from src.user_management import refund_balance
    return await refund_balance(user_id, amount)

async def handle_admin_payment_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin payment mode change."""
    from src.imports import ADMIN_CHAT_ID
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != ADMIN_CHAT_ID:
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    callback_data = query.data
    
    if callback_data == "admin_set_payment_auto":
        new_mode = PaymentMode.AUTO
    elif callback_data == "admin_set_payment_manual":
        new_mode = PaymentMode.MANUAL
    else:
        return
    
    success = await set_payment_mode(new_mode)
    
    if success:
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if new_mode == PaymentMode.AUTO else '⚪'} Auto Verification",
                    callback_data="admin_set_payment_auto"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if new_mode == PaymentMode.MANUAL else '⚪'} Manual Verification",
                    callback_data="admin_set_payment_manual"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"✅ <b>Payment mode updated</b>\n\n"
            f"Current mode: <b>{new_mode.value}</b>\n\n"
            f"<b>Auto:</b> Payments verified automatically via GlobalPay API\n"
            f"<b>Manual:</b> Admin manually confirms payments"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await query.answer("❌ Failed to update mode", show_alert=True)


# ==================== Registration ====================
def setup_payment_handlers(application: Application) -> None:
    """Register all GlobalPay-related handlers."""
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CallbackQueryHandler(balance_command, pattern="^balance$"))
    application.add_handler(CallbackQueryHandler(handle_globalpay_topup, pattern="^globalpay_topup_"))
    
    # Admin handlers
    application.add_handler(CommandHandler("payment_settings", admin_payment_settings))
    application.add_handler(CallbackQueryHandler(handle_admin_payment_mode, pattern="^admin_set_payment_"))
    application.add_handler(CommandHandler("add", admin_add_payment_command)) 

async def startup_init() -> None:
    """Initialize on bot startup."""
    await init_payment_tables()
    # Authenticate with GlobalPay on startup
    await globalpay_client.authenticate()
    logger.info("GlobalPay integration initialized")