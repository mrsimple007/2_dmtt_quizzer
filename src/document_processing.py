import os
import logging
import tempfile
import re
import zipfile
from io import BytesIO

import docx2txt
import PyPDF2

logger = logging.getLogger(__name__)

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def get_file_type_category(filename: str) -> str:
    ext = get_file_extension(filename)
    if ext in [".pdf", ".doc", ".docx", ".txt", ".rtf"]:
        return "document"
    elif ext in [".mp3", ".wav", ".ogg", ".m4a"]:
        return "audio"
    elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
        return "video"
    return None


async def extract_text_from_excel(file_bytes: bytes) -> str:
    from openpyxl import load_workbook   # lazy: only when an Excel file arrives
    """Extract text from Excel files (.xlsx)."""
    try:
        with BytesIO(file_bytes) as buf:
            wb = load_workbook(buf, data_only=True)
            text_parts = []
            
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    # Filter out None values and join with tabs
                    row_text = '\t'.join(str(cell) if cell is not None else '' for cell in row)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            return '\n'.join(text_parts)
    except Exception as e:
        logger.error(f"Excel extraction error: {e}")
        return ""


def is_valid_docx(file_bytes: bytes) -> bool:
    """Check if bytes represent a valid DOCX (ZIP) file."""
    try:
        with BytesIO(file_bytes) as buf:
            with zipfile.ZipFile(buf, 'r') as zip_ref:
                # Check for required DOCX files
                return 'word/document.xml' in zip_ref.namelist()
    except (zipfile.BadZipFile, KeyError):
        return False


# =========================================================
# PDF
# =========================================================

async def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with BytesIO(file_bytes) as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    page_text = re.sub(r'/\d+"\'.*?\w+\s*[<>].*?[\(\),\.\-]', ' ', page_text)
                    page_text = re.sub(r'KELISHILDI:.*?:', '', page_text)
                    text += page_text + "\n\n"
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
    return text

async def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        # Validate it's actually a DOCX file
        if not is_valid_docx(file_bytes):
            logger.error("File is not a valid DOCX (ZIP) format")
            return ""
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        text = docx2txt.process(tmp_path)
        os.unlink(tmp_path)
        return text or ""

    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return ""

async def extract_text_from_txt(file_bytes: bytes) -> str:
    for encoding in ["utf-8", "cp1251", "latin-1"]:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    logger.error("TXT decoding failed")
    return ""

async def extract_text_from_doc(file_bytes: bytes) -> str:
    """
    Extract text from legacy .doc files using multiple fallback methods.
    No LibreOffice required.
    """
    
    # Method 1: Try using olefile + extracting text directly
    try:
        import olefile
        
        with BytesIO(file_bytes) as buf:
            ole = olefile.OleFileIO(buf)
            
            # Check if it's a valid Word document
            if ole.exists('WordDocument'):
                # Try to extract text from the WordDocument stream
                word_stream = ole.openstream('WordDocument')
                data = word_stream.read()
                
                # Simple text extraction (this is a basic approach)
                # Real .doc format is complex, but this gets readable text
                text = ""
                for i in range(len(data)):
                    if 32 <= data[i] <= 126 or data[i] in [9, 10, 13]:  # Printable ASCII
                        text += chr(data[i])
                    elif data[i] > 127:  # Unicode characters
                        text += chr(data[i])
                
                # Clean up the extracted text
                text = re.sub(r'[^\x20-\x7E\x80-\xFF\n\r\t]+', '', text)
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = text.strip()
                
                if len(text) > 100:  # If we got substantial text
                    logger.info("Successfully extracted text from .doc using olefile")
                    return text
                    
            ole.close()
    except ImportError:
        logger.warning("olefile not installed, trying alternative method")
    except Exception as e:
        logger.warning(f"olefile extraction failed: {e}")
    
    # Method 3: Try using antiword (if available on system)
    try:
        import subprocess
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            result = subprocess.run(
                ["antiword", tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                text = result.stdout.decode('utf-8', errors='ignore')
                if text.strip():
                    logger.info("Successfully extracted text from .doc using antiword")
                    return text
        except FileNotFoundError:
            os.unlink(tmp_path)
            logger.warning("antiword not available on system")
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            logger.warning(f"antiword extraction failed: {e}")
    except Exception as e:
        logger.warning(f"Could not try antiword: {e}")
    
    # If all methods fail
    logger.error("All .doc extraction methods failed. Please install: pip install olefile")
    return ""

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    ext = get_file_extension(filename)

    if ext == ".pdf":
        return await extract_text_from_pdf(file_bytes)

    elif ext == ".docx":
        return await extract_text_from_docx(file_bytes)

    elif ext == ".doc":
        return await extract_text_from_doc(file_bytes)

    elif ext in [".xlsx", ".xls"]:  
        return await extract_text_from_excel(file_bytes)

    elif ext == ".txt":
        return await extract_text_from_txt(file_bytes)

    else:
        logger.warning(f"Unsupported file type: {ext}")
        return ""
    

