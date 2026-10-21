import os
import logging
import asyncio
from typing import Tuple, Optional
import base64
from src import GOOGLE_API_KEY

logger = logging.getLogger(__name__)
async def process_image_file(image_bytes: bytes, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[str]]:
    try:
        import google.generativeai as genai
        from src.imports import get_api_key_for_user, safe_gemini_call, GEMINI_MODELS
        import random

        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        api_key, key_num = get_api_key_for_user(user_id)
        model_name = random.choice(GEMINI_MODELS)
        
        logger.info(f"[IMAGE] Using model {model_name}, key {key_num}")

        def _sync_call():
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([
                {"mime_type": "image/png", "data": img_b64},
                "Extract all text from this image. Return only the extracted text, nothing else."
            ])
            return response.text

        loop = asyncio.get_event_loop()
        text = await asyncio.wait_for(loop.run_in_executor(None, _sync_call), timeout=60.0)

        if not text or not text.strip():
            return False, "No text found in image.", None

        return True, text.strip(), None

    except Exception as e:
        logger.error(f"[IMAGE] Error in image processing: {e}")
        return False, f"Error processing image: {e}", None