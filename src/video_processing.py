import os
import logging
import tempfile
import subprocess
from typing import Tuple, Optional
from src.audio_processing import extract_text_from_audio

logger = logging.getLogger(__name__)


async def process_video_file(
    video_bytes: bytes, 
    api_key: str, 
    output_format: str = "mp3"
) -> Tuple[bool, str, Optional[str]]:
    """
    Process video file and extract text using audio transcription.
    
    Optimized version using ffmpeg-python instead of MoviePy.
    Saves ~45 MB in dependencies.
    """
    if not api_key:
        return False, "ElevenLabs API key is required", None
    
    video_path = None
    audio_path = None
    
    try:
        # Save video bytes to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', mode='wb') as temp_video:
            temp_video.write(video_bytes)
            video_path = temp_video.name
        
        # Create temporary audio file path
        audio_path = tempfile.mktemp(suffix=f'.{output_format}')
        
        # Extract audio using ffmpeg command line
        # This is much lighter than MoviePy
        result = subprocess.run([
            'ffmpeg',
            '-i', video_path,           # Input video
            '-vn',                       # No video
            '-acodec', 'libmp3lame',    # MP3 codec
            '-ar', '44100',              # Sample rate
            '-ab', '192k',               # Bitrate
            '-y',                        # Overwrite output
            audio_path
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, "Failed to extract audio from video", None
        
        # Read the extracted audio
        with open(audio_path, 'rb') as audio_file:
            audio_bytes = audio_file.read()
        
        # Transcribe the audio
        success, message, transcript = await extract_text_from_audio(audio_bytes, api_key)
        
        return success, message, transcript
        
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please install ffmpeg: apt-get install ffmpeg")
        return False, "FFmpeg is not installed on the server", None
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout - video processing took too long")
        return False, "Video processing timeout", None
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return False, f"Error processing video: {str(e)}", None
        
    finally:
        # Clean up temporary files
        for path in [video_path, audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {path}: {e}")


# Alternative: Pure Python implementation without FFmpeg
async def process_video_file_fallback(
    video_bytes: bytes,
    api_key: str,
    output_format: str = "mp3"
) -> Tuple[bool, str, Optional[str]]:
    """
    Fallback for environments without FFmpeg.
    
    NOTE: This extracts raw audio without re-encoding.
    Works for some formats but not all.
    """
    try:
        import av  # PyAV - lightweight alternative
        
        video_path = None
        audio_path = None
        
        try:
            # Save video to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', mode='wb') as f:
                f.write(video_bytes)
                video_path = f.name
            
            # Extract audio using PyAV
            audio_path = tempfile.mktemp(suffix=f'.{output_format}')
            
            input_container = av.open(video_path)
            output_container = av.open(audio_path, 'w')
            
            # Get audio stream
            audio_stream = next((s for s in input_container.streams if s.type == 'audio'), None)
            if not audio_stream:
                return False, "No audio stream found in video", None
            
            # Copy audio stream
            output_stream = output_container.add_stream('mp3', rate=44100)
            
            for packet in input_container.demux(audio_stream):
                for frame in packet.decode():
                    for packet in output_stream.encode(frame):
                        output_container.mux(packet)
            
            # Flush
            for packet in output_stream.encode():
                output_container.mux(packet)
            
            input_container.close()
            output_container.close()
            
            # Read audio and transcribe
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            return await extract_text_from_audio(audio_bytes, api_key)
            
        finally:
            for path in [video_path, audio_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
                        
    except ImportError:
        return False, "Neither FFmpeg nor PyAV available for video processing", None
    except Exception as e:
        logger.error(f"Fallback video processing failed: {e}")
        return False, f"Error: {str(e)}", None