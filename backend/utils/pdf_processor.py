import os
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
import logging
import platform
import gc
import base64
import uuid
from pathlib import Path
from io import BytesIO

logger = logging.getLogger(__name__)

# Set Poppler path for Windows
POPPLER_PATH = os.getenv('POPPLER_PATH')

if platform.system() == 'Windows' and not POPPLER_PATH:
    # Fallback to local project path if not in environment
    local_poppler = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bin', 'poppler', 'Library', 'bin')
    if os.path.exists(local_poppler):
        POPPLER_PATH = local_poppler
    else:
        poppler_root = Path(__file__).resolve().parents[2] / 'bin' / 'poppler'
        candidates = sorted(poppler_root.glob('*/Library/bin'))
        POPPLER_PATH = next((str(path) for path in candidates if (path / 'pdftoppm.exe').is_file()), None)
        if not POPPLER_PATH:
            logger.warning('No bundled Poppler found; using system PATH')

class PDFProcessor:
    @staticmethod
    def page_count(pdf_path):
        count = len(PdfReader(pdf_path).pages)
        maximum = int(os.getenv('PDF_MAX_PAGES', '200'))
        if not 0 < count <= maximum:
            raise ValueError(f'Document must contain 1 to {maximum} pages')
        return count

    @staticmethod
    def render_page(pdf_path, index):
        images = convert_from_path(pdf_path, dpi=150, first_page=index + 1,
                                   last_page=index + 1, poppler_path=POPPLER_PATH,
                                   timeout=120, size=2500, thread_count=1)
        if len(images) != 1:
            for image in images:
                image.close()
            raise ValueError('Unable to render the requested page')
        return images[0]

    @staticmethod
    def extract_text_from_pdf(pdf_path):
        """Extract complete text only when every page has a usable text layer."""
        try:
            PDFProcessor.page_count(pdf_path)
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ''
                if len(page_text.strip()) < 20:
                    raise ValueError('Page requires visual extraction')
                text += page_text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    @staticmethod
    def convert_pdf_to_images(pdf_path, max_pages=36):
        """Convert PDF to images for Gemini vision API (limited to first 36 pages)"""
        try:
            logger.info(f"Converting PDF to images: {pdf_path}")
            if len(PdfReader(pdf_path).pages) > max_pages:
                raise ValueError(f'PDF exceeds the supported {max_pages} pages; split it explicitly before processing')
            # Preserve handwriting detail; page limits are checked before rendering.
            if POPPLER_PATH:
                images = convert_from_path(pdf_path, dpi=150, poppler_path=POPPLER_PATH, last_page=max_pages, timeout=120)
            else:
                images = convert_from_path(pdf_path, dpi=150, last_page=max_pages, timeout=120)
            
            logger.info(f"Converted {len(images)} pages to images")
            return images
        except Exception as e:
            raise Exception(f"Error converting PDF to images: {str(e)}")
    
    @staticmethod
    def extract_text_from_images_via_gemini(images, gemini_service, document_kind='student'):
        """Use Gemini vision API to extract text from images (much faster than EasyOCR)"""
        try:
            logger.info(f"Extracting text from {len(images)} images using Gemini vision...")
            extracted_text = ""
            
            for idx, image in enumerate(images):
                try:
                    logger.info(f"Processing page {idx + 1}/{len(images)} with Gemini vision...")
                    
                    # Convert PIL image to bytes for Gemini
                    img_byte_arr = BytesIO()
                    image.save(img_byte_arr, format='JPEG', quality=70, optimize=True)
                    img_byte_arr.seek(0)
                    img_base64 = base64.standard_b64encode(img_byte_arr.getvalue()).decode()
                    
                    # Use Gemini vision to extract text with built-in retry and key rotation logic
                    prompt = [
                        ("Extract all student answer text faithfully, excluding teacher grading marks. Do not invent missing text. "
                         if document_kind == 'student' else
                         "Extract all printed and handwritten text faithfully, including question numbers, marks, optional-question rules, tables and marking instructions. Do not invent missing text. ")
                        + "Return ONLY extracted text. For a genuinely blank page return [BLANK_PAGE]. Mark any unreadable answer region [UNREADABLE]; never guess.",
                        {
                            "mime_type": "image/jpeg",
                            "data": img_base64
                        }
                    ]
                    response = gemini_service._generate_with_retry(prompt)
                    
                    # Safely extract text (Gemini throws ValueError on empty images if we call .text directly)
                    try:
                        page_text = response.text.strip() if getattr(response, 'parts', None) or hasattr(response, 'text') else "[No text detected]"
                    except ValueError:
                        page_text = "[No text detected]"
                    extracted_text += f"\n--- Page {idx + 1} ---\n{page_text}\n"
                    
                    # Cleanup
                    del image
                    del img_byte_arr
                    gc.collect()
                    
                except Exception as page_error:
                    logger.warning(f"Error processing page {idx + 1}: {str(page_error)}")
                    raise
            
            logger.info("Gemini vision extraction completed")
            return extracted_text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text via Gemini: {str(e)}")
            raise
    
    @staticmethod
    def save_uploaded_file(file, upload_folder):
        """Save uploaded file and return path"""
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        file_path = os.path.join(upload_folder, uuid.uuid4().hex + os.path.splitext(file.filename)[1].lower())
        file.save(file_path)
        return file_path
