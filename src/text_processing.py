import logging
from datetime import datetime
import re
from typing import Optional

logger = logging.getLogger(__name__)

MAX_TOKEN_LIMIT = 30000

def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def truncate_text(text: str, max_length: int = 3000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

async def truncate_text(text: str, max_length: int = 16000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0]

def clean_text(text: str) -> str:
    text = re.sub(r'[^\w\s\.,!?;:\'\"()\[\]{}\-–—/]', ' ', text)
    
    text = re.sub(r'\s+', ' ', text)
    
    text = re.sub(r'\s[_\-–—/]\s', ' ', text)
    
    patterns = [
        r'/\d+["\']',  # Matches patterns like /9"
        r'_[a-zA-Z]+<',  # Matches patterns like _l<
        r'>[a-zA-Z]+\s',  # Matches patterns like >l
        r'\s[a-zA-Z]\s',  # Single letters
        r'[<>]',  # Remove < and >
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, ' ', text)
    
    # Clean up the result
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text

def detect_language(text: str) -> str:
    """Detect the language of the text based on character patterns."""
    # Count characters in different scripts
    cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    uzbek = len(re.findall(r'[ўқғҳ]', text))
    
    # Simple heuristic for language detection
    if uzbek > 0 or ('oʻzbek' in text.lower()):
        return 'uz'
    elif cyrillic > latin:
        return 'ru'
    else:
        return 'en' 