import logging
import aiohttp
import asyncio
from typing import Optional, Tuple
import re

logger = logging.getLogger(__name__)

class WebContentExtractor:
    """Lightweight web scraper using only aiohttp + BeautifulSoup"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def is_robot_check(self, text: str) -> bool:
        """Check if page shows robot verification"""
        robot_phrases = [
            "please confirm that you are not a robot",
            "we're sorry, but it looks like requests sent from your device are automated",
            "captcha",
            "verify you are human",
            "robot check",
            "automated request"
        ]
        return any(phrase.lower() in text.lower() for phrase in robot_phrases)

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove robot check messages
        text = re.sub(r'Please confirm that you and not a robot.*?Why might th\.\.\.', '', text, flags=re.DOTALL)
        text = re.sub(r"We're sorry, but it looks like requests sent from your device are automated.*?Why might th\.\.\.", '', text, flags=re.DOTALL)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    async def extract_with_requests(self, url: str, timeout: int = 30) -> Tuple[bool, str]:
        """Extract content using lightweight aiohttp"""
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=self.headers, 
                    timeout=timeout_config, 
                    allow_redirects=True,
                    ssl=False
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        from bs4 import BeautifulSoup   # lazy: only when a link is sent
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove unwanted elements
                        for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'ads', 'iframe']):
                            element.decompose()
                        
                        # Try to find main content
                        main_content = (
                            soup.find('main') or 
                            soup.find('article') or 
                            soup.find('div', class_='content') or 
                            soup.find('div', class_='main') or
                            soup
                        )
                        
                        # Extract text
                        text = main_content.get_text(separator='\n')
                        text = self.clean_text(text)
                        
                        if self.is_robot_check(text):
                            return False, "Robot verification required - content may be incomplete"
                        
                        if len(text) < 100:
                            return False, "Insufficient content extracted"
                        
                        return True, text
                    else:
                        return False, f"HTTP {response.status}: Could not access website"
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting {url}")
            return False, "Request timeout - website took too long to respond"
        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            return False, f"Error: {str(e)}"

    async def extract_with_retry(self, url: str, max_retries: int = 3) -> Tuple[bool, str]:
        """Extract with automatic retry logic"""
        for attempt in range(max_retries):
            success, result = await self.extract_with_requests(url)
            
            if success:
                return True, result
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.info(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        return False, f"Failed after {max_retries} attempts: {result}"


async def extract_text_from_url(url: str) -> str:
    """
    Main function to extract text from URL.
    
    This is a drop-in replacement for the old function.
    Removed Selenium and Scrapy dependencies - now uses only aiohttp + BeautifulSoup.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    extractor = WebContentExtractor()
    success, result = await extractor.extract_with_retry(url, max_retries=3)
    
    if success:
        return result
    else:
        return f"Error: Could not extract content from URL. {result}"


# Backward compatibility
async def extract_with_selenium(url: str) -> Tuple[bool, str]:
    """Deprecated - redirects to lightweight method"""
    logger.warning("extract_with_selenium is deprecated, using lightweight method instead")
    extractor = WebContentExtractor()
    return await extractor.extract_with_requests(url)