import os
import logging
import tempfile
import aiohttp
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v1"

async def extract_text_from_audio(audio_bytes: bytes, api_key: str) -> Tuple[bool, str, Optional[str]]:
    logger.info(f"Starting audio extraction. Audio size: {len(audio_bytes)} bytes")
    logger.debug(f"API key exists: {bool(api_key)}")

    if not api_key:
        logger.error("No API key provided")
        return False, "ElevenLabs API key is required", None
    
    temp_path = None
    
    try:
        temp_path = tempfile.mktemp(suffix='.mp3')
        logger.debug(f"Temp audio path: {temp_path}")
        
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        logger.debug(f"Audio file saved, size: {os.path.getsize(temp_path)} bytes")
        
        headers = {
            "xi-api-key": api_key
        }
        
        form_data = aiohttp.FormData()
        form_data.add_field('file', open(temp_path, 'rb'), filename='audio.mp3', content_type='audio/mpeg')
        form_data.add_field('model_id', DEFAULT_MODEL)
        
        logger.debug(f"Sending request to ElevenLabs API at {ELEVENLABS_API_URL}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ELEVENLABS_API_URL,
                headers=headers,
                data=form_data,
                timeout=300
            ) as response:
                logger.debug(f"Response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ElevenLabs API error (Status {response.status}): {error_text}")
                    return False, f"Transcription failed with status {response.status}", None
                
                result = await response.json()
                logger.debug(f"API response: {result}")
                
                if 'text' in result:
                    logger.info(f"Transcription successful, text length: {len(result['text'])}")
                    return True, "Transcription successful", result['text']
                else:
                    logger.error("No text found in transcription result")
                    return False, "No text found in transcription result", None
    
    except aiohttp.ClientError as e:
        logger.error(f"ElevenLabs API request error: {e}")
        return False, f"API request failed: {str(e)}", None
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return False, f"Error processing audio: {str(e)}", None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Removed temp audio file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary audio file: {e}")



async def save_transcription_to_temp_file(transcript_text: str) -> str:
    transcript_path = tempfile.mktemp(suffix='.txt')
    
    try:
        with open(transcript_path, 'w', encoding='utf-8') as transcript_file:
            transcript_file.write(transcript_text)
        return transcript_path
    except Exception as e:
        logger.error(f"Error saving transcription to temp file: {e}")
        raise