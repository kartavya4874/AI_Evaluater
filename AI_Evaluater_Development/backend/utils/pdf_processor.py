import os
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from PIL import Image
import tempfile
import numpy as np
import logging
import platform
import time
import base64
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
        logger.warning("Poppler path not found in environment and local 'bin/poppler' not found.")

class PDFProcessor:
    @staticmethod
    def extract_text_from_pdf(pdf_path):
        \"\"\"Extract plain text from PDF (for model answers)\"\"\"
        try:
            reader = PdfReader(pdf_path)
            text = \"\"\"
            for page in reader.pages:
                text += page.extract_text() + \"\\n\"
            return text.strip()
        except Exception as e:
            raise Exception(f\"Error extracting text from PDF: {str(e)}\")
    
    @staticmethod
    def convert_pdf_to_images(pdf_path, max_pages=36):
        \"\"\"Convert PDF to images for vision OCR (limited to first max_pages pages)\"\"\"
        try:
            logger.info(f\"Converting PDF to images: {pdf_path}\")
            # Low DPI is fine — the vision model handles low-res images well
            if POPPLER_PATH:
                images = convert_from_path(pdf_path, dpi=50, poppler_path=POPPLER_PATH, last_page=max_pages)
            else:
                images = convert_from_path(pdf_path, dpi=50, last_page=max_pages)
            
            logger.info(f\"Converted {len(images)} pages to images\")
            return images
        except Exception as e:
            raise Exception(f\"Error converting PDF to images: {str(e)}\")

    @staticmethod
    def extract_text_from_images_via_gemini(images, gemini_service):
        \"\"\"\n        Use the vLLM vision model to extract handwritten text from page images with retries.\n        The parameter is named 'gemini_service' for backwards compatibility but\n        it now points to the vLLM-backed GeminiService.\n        \"\"\"\n        MAX_ATTEMPTS = 3\n        extracted_text = \"\"\n        for idx, image in enumerate(images):\n            page_processed = False\n            page_text = \"[Initial attempt]\"\n            retry_success = False\n            \n            # Attempt up to MAX_ATTEMPTS times for this page\n            for attempt in range(MAX_ATTEMPTS): \n                try:\n                    logger.info(f\"Attempt {attempt + 1}/{MAX_ATTEMPTS} processing page {idx + 1} with vLLM vision…\")\n                    # Build the multimodal prompt\n                    prompt = [\n                        \"Extract all student handwritten text, but DO NOT extract any red-pen grading marks, circle totals, or overall grades written by teachers. Return ONLY the extracted text, nothing else.\",\n                        {\n                            \"mime_type\": \"image/jpeg\",\n                            \"data\": img_base64\n                        }\n                    ]\n                    # Attempt to call the service\n                    response = gemini_service._generate_with_retry(prompt)\n                    \n                    # Safely extract text on success\n                    page_text = response.text.strip() if hasattr(response, 'text') and response.text else \"[No text detected]\"\n                    retry_success = True\n                    break # Success, break retry loop\n                except Exception as e:\n                    if attempt < MAX_ATTEMPTS - 1:\n                        wait_time = 2 ** attempt * 2  # Exponential backoff (2s, 4s...)\n                        logger.warning(f\"Attempt {attempt + 1}/{MAX_ATTEMPTS} failed for page {idx + 1}: {str(e)}. Retrying in {wait_time} seconds....\")\n                        import time\n                        time.sleep(wait_time)\n                    else:\n                        # Final attempt failed, re-raise to be caught by the outer 'except'\n                        raise e # Re-raise to be caught by the outer 'try/except' block\n            \n            if retry_success: \n                extracted_text += f\"\\n--- Page {idx + 1} ---\\n{page_text}\\n\"\n            else:\n                # This path is hit if all attempts fail.\n                pass\n        \n        return extracted_text.strip()


    @classmethod
    def extract_text_from_images(cls, images):
        \"\"\"Extract text from images using EasyOCR with memory optimization (fallback)\"\"\"\n        try:\n            import easyocr\n            logger.info(f\"Extracting text from {len(images)} images using EasyOCR…\")\n            reader = easyocr.Reader(['en'], gpu=False)\n            extracted_text = \"\"\n            \n            for idx, image in enumerate(images):\n                try:\n                    logger.info(f\"Processing page {idx + 1}/{len(images)}…\")\n                    \n                    # Resize image to 40% to save memory\n                    new_width = max(int(image.width * 0.4), 400)\n                    new_height = int(image.height * 0.4)\n                    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)\n                    \n                    # Convert PIL Image to numpy array for EasyOCR\n                    img_array = np.array(resized_image)\n                    \n                    # Perform OCR\n                    results = reader.readtext(img_array, detail=0, paragraph=False)\n                    \n                    # Combine results\n                    page_text = \"\\n\".join(results) if results else \"[No text detected]\"\n                    extracted_text += f\"\\n--- Page {idx + 1} ---\\n{page_text}\\n\"\n                    \n                    # Explicit memory cleanup (relying on scope exit & GC)\n                    del resized_image\n                    del img_array\n                    del image\n                except Exception as page_error:\n                    logger.warning(f\"Error processing page {idx + 1}: {str(page_error)}\")\n                    extracted_text += f\"\\n--- Page {idx + 1} ---\\n[Error processing page]\\n\"\n                finally:\n                    pass # Empty finally block to consume the 'del' statements cleanup intent\n            \n            logger.info(\"EasyOCR text extraction completed\")\n            return extracted_text.strip()\n        except Exception as e:\n            logger.error(f\"Error extracting text: {str(e)}\")\n            raise Exception(f\"Error extracting text from images via EasyOCR: {str(e)}\")


    @staticmethod
    def save_uploaded_file(file, upload_folder):\n        \"\"\"Save uploaded file and return path\"\"\"\n        if not os.path.exists(upload_folder):\n            os.makedirs(upload_folder)\n        \n        file_path = os.path.join(upload_folder, file.filename)\n        file.save(file_path)\n        return file_path