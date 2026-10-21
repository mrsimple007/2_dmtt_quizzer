import os
import logging
from datetime import datetime, timezone
import asyncio
import re
import uuid
import json
import random
import time
import threading
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

# Users who never pay (comma separated Telegram IDs in .env). Empty = nobody.
# Defined this early on purpose: other modules import from here in a circle.
FREE_USER_IDS = {int(x) for x in os.environ.get("FREE_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}


def is_free_user(user_id) -> bool:
    try:
        return int(user_id) in FREE_USER_IDS
    except (TypeError, ValueError):
        return False


from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes, PollAnswerHandler, InlineQueryHandler
)
from telegram.constants import ParseMode

from supabase import create_client, Client
import google.generativeai as genai

from src.prompts_summarize import *
from src.quiz_service import *
from src.audio_processing import *
from src.document_processing import *
from src.web_processing import *
from src.user_management import *
from src.text_processing import *
from src import ELEVENLABS_API_KEY
from payment_integration_new import *
from telegram.ext import ChatMemberHandler
from handlers.share import *
from handlers.admin_contact import *


# Logging setup

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Silence noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.ExtBot").setLevel(logging.WARNING)


# BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_SIMPLELEARNINGUZ")
BOT_TOKEN = os.environ.get("DMTT_QUIZ_BOT_TOKEN")


SUPABASE_URL = os.environ.get("QUIZ_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("QUIZ_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ACTIVITY_SUPABASE_URL = os.environ.get("ACTIVITY_SUPABASE_URL")
ACTIVITY_SUPABASE_KEY = os.environ.get("ACTIVITY_SUPABASE_KEY")
supabase_activity = create_client(ACTIVITY_SUPABASE_URL, ACTIVITY_SUPABASE_KEY)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


REFERRAL_BONUS = 200000  # Balance units awarded for referral
POINTS_FOR_QUIZ=5

# Prices in UZS
PREMIUM_PRICE_UZS = 30000  # 30,000 UZS per month
PPT_COST_UZS = 2000  # 2000 UZS per PPT
INITIAL_BALANCE_UZS = 6000  # 6,000 UZS initial balance

# Card information for manual payments
# CARD_NUMBER = "4916 9903 1823 1617"  
CARD_NUMBER = "4073 4200 3711 6443"
CARD_NUMBER_2 = "9860 1866 0119 6766"



NOTIFICATION_ADMIN_IDS = [
    8437026582,  # MR - always gets notifications
    # 999932510,
    # 8126290272  # MR 2
]


FREE_USER_IDS = {"8498397733"}

ADMIN_USERNAME= "@SimpleLearn_main_admin"
ADMIN_CHAT_ID="8437026582" #MR - main admin

# ADMIN_USERNAME = "@MrSimple07"
# ADMIN_CHAT_ID = "999932510"     # MrSimple07


# ADMIN_USERNAME= "@SimpleLearn_admin"
# ADMIN_CHAT_ID="8126290272" #MR_2 



# ADMIN_CHAT_ID="6352649041" #Akhmadjon
# ADMIN_USERNAME="@extra_l1fe"


GOOGLE_API_KEY = [
    os.environ.get("GOOGLE_API_KEY", ""),
    os.environ.get("GOOGLE_API_KEY_2", ""),
    os.environ.get("GOOGLE_API_KEY_3", ""),
    os.environ.get('GOOGLE_API_KEY_4',''),
    os.environ.get('GOOGLE_API_KEY_5',""),
    os.environ.get('GOOGLE_API_KEY_6',""),
    os.environ.get('GOOGLE_API_KEY_7',""),
    os.environ.get('GOOGLE_API_KEY_8',""),
    os.environ.get('GOOGLE_API_KEY_9',""),
    os.environ.get('GOOGLE_API_KEY_10',""),
    os.environ.get('GOOGLE_API_KEY_11',""),
    os.environ.get('GOOGLE_API_KEY_12',""),
    os.environ.get('GOOGLE_API_KEY_13',""),
    os.environ.get('GOOGLE_API_KEY_14',""),
    os.environ.get('SIMPLE_TRAVEL_1',""),
]

# Filter out empty API keys and create (key, number) tuples
GOOGLE_API_KEYS = [(k, f"#{i+1}") for i, k in enumerate(GOOGLE_API_KEY) if k and k.strip()]

# Gemini Models
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",    
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview"
    ]

GEMINI_MODEL = "gemini-2.5-flash"  
DEFAULT_TEMPERATURE = 0.7

# One semaphore per API key (serializes requests per key)
KEY_CONCURRENCY = 3  
key_semaphores: Dict[str, asyncio.Semaphore] = {}

# Rate limiting per API key (not per model, not per combo)
api_last_used: Dict[str, float] = defaultdict(float)
MIN_API_INTERVAL = 6.0  # Seconds between requests on same key

# Global backpressure (prevents Telegram stampede)
GLOBAL_SEMAPHORE = asyncio.Semaphore(20)  

# User to API key assignment (for sticky routing)
user_api_assignments: Dict[int, Tuple[str, str]] = {}  
assignment_lock = threading.Lock()

# Key health tracking
key_failure_count: Dict[str, int] = defaultdict(int)
key_last_failure_time: Dict[str, float] = defaultdict(float)
MAX_FAILURES_BEFORE_COOLDOWN = 5
FAILURE_RESET_TIME = 300.0  # 5 minutes
KEY_COOLDOWN_AFTER_FAILURES = 60.0  # 1 minute cooldown after repeated failures


def initialize_key_semaphores():
    """Initialize one semaphore per API key"""
    global key_semaphores
    key_semaphores = {
        key: asyncio.Semaphore(KEY_CONCURRENCY)
        for key, _ in GOOGLE_API_KEYS
    }
    logger.info(f"Initialized {len(key_semaphores)} key semaphores with concurrency={KEY_CONCURRENCY}")


def get_healthy_keys() -> List[Tuple[str, str]]:
    """Get list of healthy API keys (not in cooldown)"""
    current_time = time.time()
    healthy = []
    
    for key, num in GOOGLE_API_KEYS:
        failures = key_failure_count[key]
        last_failure = key_last_failure_time[key]
        
        # Reset failure count if enough time has passed
        if current_time - last_failure > FAILURE_RESET_TIME:
            key_failure_count[key] = 0
            failures = 0
        
        # Check if key is in cooldown
        in_cooldown = (failures >= MAX_FAILURES_BEFORE_COOLDOWN and 
                      current_time - last_failure < KEY_COOLDOWN_AFTER_FAILURES)
        
        if not in_cooldown:
            healthy.append((key, num))
    
    return healthy if healthy else GOOGLE_API_KEYS  


def get_api_key_for_user(user_id: Optional[int] = None) -> Tuple[str, str]:
    """Get or assign an API key for a user (sticky routing)"""
    with assignment_lock:
        # Check if user has existing assignment
        if user_id and user_id in user_api_assignments:
            api_key, key_num = user_api_assignments[user_id]
            
            # Verify key is still healthy
            healthy_keys = get_healthy_keys()
            if any(k == api_key for k, _ in healthy_keys):
                logger.debug(f"Reusing key {key_num} for user {user_id}")
                return api_key, key_num
            else:
                logger.debug(f"Key {key_num} unhealthy, reassigning user {user_id}")
                del user_api_assignments[user_id]
        
        # Get healthy keys
        healthy_keys = get_healthy_keys()
        
        if not healthy_keys:
            logger.warning("No healthy keys available, using first key")
            return GOOGLE_API_KEYS[0]
        
        # Randomly select from healthy keys for even distribution
        selected_key, selected_num = random.choice(healthy_keys)
        
        # Assign to user
        if user_id:
            user_api_assignments[user_id] = (selected_key, selected_num)
        
        logger.info(f"Assigned key {selected_num} to user {user_id}")
        return selected_key, selected_num


async def safe_gemini_call(
    api_key: str,
    model_name: str,
    prompt: str,
    key_number: str = "Unknown",
    timeout: float = 160.0
) -> str:
    """Make a safe Gemini API call with rate limiting and serialization"""
    # Ensure semaphore exists
    if api_key not in key_semaphores:
        key_semaphores[api_key] = asyncio.Semaphore(KEY_CONCURRENCY)
    
    semaphore = key_semaphores[api_key]
    
    # Acquire per-key semaphore (serializes requests on this key)
    async with semaphore:
        # Enforce rate limit
        now = time.time()
        wait_time = MIN_API_INTERVAL - (now - api_last_used[api_key])
        if wait_time > 0:
            logger.debug(f"Rate limiting key {key_number}: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        loop = asyncio.get_event_loop()
        
        def _sync_call():
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=DEFAULT_TEMPERATURE,
                )
            )
            return response.text
        
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_call),
                timeout=timeout
            )
            
            # Reset failure count on success
            key_failure_count[api_key] = 0
            
            return result
            
        finally:
            # Always update last used time
            api_last_used[api_key] = time.time()


async def async_generate_content_with_retry(
    prompt: str, 
    user_id: Optional[int] = None,
    max_attempts: int = 10
) -> Optional[str]:
    """Generate content with retry logic using user-sticky API key assignment"""
    last_error = None
    tried_models = set()
    
    # Global backpressure (prevents stampede)
    async with GLOBAL_SEMAPHORE:
        for attempt in range(max_attempts):
            try:
                # Get API key for user
                api_key, key_num = get_api_key_for_user(user_id)
                
                # Select model (try different models on retry)
                available_models = [m for m in GEMINI_MODELS if m not in tried_models]
                if not available_models:
                    available_models = GEMINI_MODELS
                    tried_models.clear()
                
                model_name = random.choice(available_models)
                tried_models.add(model_name)
                
                logger.info(f"[Attempt {attempt + 1}/{max_attempts}] User {user_id}: {model_name} + Key {key_num}")
                
                # Make the call through safe wrapper
                response_text = await safe_gemini_call(
                    api_key=api_key,
                    model_name=model_name,
                    prompt=prompt,
                    key_number=key_num,
                    timeout=260.0
                )
                
                logger.info(f"✓ SUCCESS for user {user_id} with {model_name} {key_num}")
                return response_text
                
            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning(f"✗ Timeout (attempt {attempt + 1}/{max_attempts})")
                
                # Mark key as having an issue
                if user_id and user_id in user_api_assignments:
                    with assignment_lock:
                        key = user_api_assignments[user_id][0]
                        key_failure_count[key] += 1
                        key_last_failure_time[key] = time.time()
                        
                        # Clear assignment to try different key next time
                        if key_failure_count[key] >= MAX_FAILURES_BEFORE_COOLDOWN:
                            logger.warning(f"Key {key_num} hit failure threshold, will cooldown")
                            del user_api_assignments[user_id]
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(3)
                
            except Exception as e:
                error_str = str(e).lower()
                last_error = error_str
                
                logger.warning(f"✗ Error: {str(e)[:150]}")
                
                # Check if quota/rate error
                is_quota_error = any(keyword in error_str for keyword in [
                    "429", "quota", "rate", "resource_exhausted", "exhausted", 
                    "limit", "too many requests"
                ])
                
                if is_quota_error:
                    logger.warning(f"Quota error detected on key {key_num}")
                    
                    # Mark key as having issues
                    if user_id and user_id in user_api_assignments:
                        with assignment_lock:
                            key = user_api_assignments[user_id][0]
                            key_failure_count[key] += 1
                            key_last_failure_time[key] = time.time()
                            
                            # Force reassignment
                            del user_api_assignments[user_id]
                
                if attempt < max_attempts - 1:
                    delay = 5 if is_quota_error else 3
                    await asyncio.sleep(delay)
        
        logger.error(f"ALL ATTEMPTS EXHAUSTED for user {user_id}. Last error: {last_error}")
        return None


# Backward compatibility wrappers
def generate_content_with_retry(prompt: str, max_attempts: int = None) -> Optional[str]:
    """Sync wrapper for backward compatibility"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        async_generate_content_with_retry(prompt, user_id=None, max_attempts=max_attempts or 10)
    )


async def async_get_llm_with_retry(max_attempts: int = None):
    """Get LLM instance with retry logic (kept for backward compatibility)"""
    # This is tricky - we can't really return an LLM with sticky routing
    # Just get a random healthy key and return an LLM with it
    # (langchain imported lazily)
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key, key_num = get_api_key_for_user(user_id=None)
    
    try:
        os.environ["GOOGLE_API_KEY"] = api_key
        llm = ChatGoogleGenerativeAI(
            model=random.choice(GEMINI_MODELS),
            temperature=DEFAULT_TEMPERATURE,
            max_retries=0
        )
        logger.info(f"Created LLM with key {key_num}")
        return llm
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        return None


def get_llm_with_retry(max_attempts: int = None):
    """Sync wrapper for get_llm_with_retry"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(async_get_llm_with_retry(max_attempts))


def invoke_llm_with_retry(prompt: str, max_attempts: int = None) -> Optional[str]:
    """Sync wrapper for invoke with retry"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        async_generate_content_with_retry(prompt, user_id=None, max_attempts=max_attempts or 10)
    )


async def async_invoke_llm_with_retry(prompt: str, max_attempts: int = None) -> Optional[str]:
    """Async invoke with retry"""
    return await async_generate_content_with_retry(prompt, user_id=None, max_attempts=max_attempts or 10)


# Kept for backward compatibility
def get_gemini_with_key(api_key: str, model_name: str):
    """Create a fresh Gemini model with specific API key and model"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        logger.info(f"Created Gemini model '{model_name}' with key ending: ...{api_key[-4:]}")
        return model
    except Exception as e:
        logger.error(f"Failed to create model '{model_name}' with key ...{api_key[-4:]}: {e}")
        return None


def get_llm_with_key(api_key):
    """Original function - kept for backward compatibility with LangChain"""
    if not api_key or not api_key.strip():
        raise ValueError("API key is empty or None")
    os.environ["GOOGLE_API_KEY"] = api_key
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.7,
        max_retries=0
    )


def get_quota_status() -> Dict:
    """Get current API usage statistics"""
    with assignment_lock:
        current_time = time.time()
        
        total_keys = len(GOOGLE_API_KEYS)
        healthy_keys = get_healthy_keys()
        
        # Count keys in cooldown
        cooldown_keys = sum(
            1 for key, _ in GOOGLE_API_KEYS
            if (key_failure_count[key] >= MAX_FAILURES_BEFORE_COOLDOWN and
                current_time - key_last_failure_time[key] < KEY_COOLDOWN_AFTER_FAILURES)
        )
        
        return {
            "total_keys": total_keys,
            "total_models": len(GEMINI_MODELS),
            "total_combinations": total_keys * len(GEMINI_MODELS),
            "healthy_keys": len(healthy_keys),
            "cooldown_keys": cooldown_keys,
            "active_users": len(user_api_assignments),
            "key_concurrency": KEY_CONCURRENCY,
            "min_api_interval": MIN_API_INTERVAL,
            "global_semaphore_limit": GLOBAL_SEMAPHORE._value,
            "availability_percent": (len(healthy_keys) / total_keys * 100) if total_keys > 0 else 0,
            "load_distribution": "Balanced" if len(healthy_keys) > total_keys * 0.7 else "Degraded"
        }


def reset_exhausted_keys():
    """Reset the exhausted combinations tracker (backward compatibility)"""
    reset_exhausted_combinations()


def reset_exhausted_combinations():
    """Reset all API assignments and health tracking"""
    with assignment_lock:
        user_api_assignments.clear()
        api_last_used.clear()
        key_failure_count.clear()
        key_last_failure_time.clear()
        logger.info("Reset all API assignments and health tracking")


def clear_user_assignment(user_id: int):
    """Clear API assignment for specific user"""
    with assignment_lock:
        if user_id in user_api_assignments:
            del user_api_assignments[user_id]
            logger.info(f"Cleared API assignment for user {user_id}")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LANGUAGE, CONTENT, PROCESSING = range(3)



from functools import lru_cache
import time

# Simple in-memory cache with TTL
class UserDataCache:
    def __init__(self, ttl=300):  # 5 minutes default
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())
    
    def invalidate(self, key):
        if key in self.cache:
            del self.cache[key]

# Global cache instance
user_cache = UserDataCache(ttl=300)

async def get_user_language_cached(user_id: int) -> str:
    cache_key = f"lang_{user_id}"
    cached = user_cache.get(cache_key)
    if cached:
        return cached
    
    language = await get_user_language(user_id)
    user_cache.set(cache_key, language)
    return language

# Cached user settings
async def get_user_settings_batch(user_id: int) -> dict:
    from src.user_management import get_user_balance, get_user_language, get_user_quiz_type, get_user_quiz_time, get_user_quiz_questions, get_user_premium_status
    """Get all user settings in one call instead of multiple queries"""
    cache_key = f"settings_{user_id}"
    cached = user_cache.get(cache_key)
    if cached:
        return cached
    
    # Fetch all settings in parallel
    settings = await asyncio.gather(
        get_user_language(user_id),
        get_user_quiz_type(user_id),
        get_user_quiz_time(user_id),
        get_user_quiz_questions(user_id),
        get_user_premium_status(user_id),
        return_exceptions=True
    )
    
    result = {
        'language': settings[0] if not isinstance(settings[0], Exception) else 'uz',
        'quiz_type': settings[1] if not isinstance(settings[1], Exception) else 'mc',
        'quiz_time': settings[2] if not isinstance(settings[2], Exception) else 30,
        'quiz_questions': settings[3] if not isinstance(settings[3], Exception) else 5,
        'is_premium': settings[4] if not isinstance(settings[4], Exception) else False,
    }
    
    user_cache.set(cache_key, result)
    return result