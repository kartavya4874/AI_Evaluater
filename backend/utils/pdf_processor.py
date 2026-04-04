import os
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from PIL import Image
import tempfile
import numpy as np
import logging
import platform
import gc
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
        """Extract plain text from PDF (for model answers)"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    @staticmethod
    def convert_pdf_to_images(pdf_path, max_pages=36):
        """Convert PDF to images for Gemini vision API (limited to first 36 pages)"""
        try:
            logger.info(f"Converting PDF to images: {pdf_path}")
            # Very low DPI for speed - Gemini can read low-res images fine
            if POPPLER_PATH:
                images = convert_from_path(pdf_path, dpi=50, poppler_path=POPPLER_PATH, last_page=max_pages)
            else:
                images = convert_from_path(pdf_path, dpi=50, last_page=max_pages)
            
            logger.info(f"Converted {len(images)} pages to images")
            return images
        except Exception as e:
            raise Exception(f"Error converting PDF to images: {str(e)}")
    
    @staticmethod
    def extract_text_from_images_via_gemini(images, gemini_service):
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
                        "Extract all student handwritten text, but DO NOT extract any red-pen grading marks, circle totals, or overall grades written by teachers. Return ONLY the extracted text, nothing else.",
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
                    extracted_text += f"\n--- Page {idx + 1} ---\n[Error: {str(page_error)}]\n"
                    gc.collect()
                    continue
            
            logger.info("Gemini vision extraction completed")
            return extracted_text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text via Gemini: {str(e)}")
            raise Exception(f"Error extracting text from images: {str(e)}")
    
    @classmethod
    def extract_text_from_images(cls, images):
        """Extract text from images using EasyOCR with memory optimization"""
        try:
            logger.info(f"Extracting text from {len(images)} images...")
            reader = cls.get_ocr_reader()
            extracted_text = ""
            
            for idx, image in enumerate(images):
                try:
                    logger.info(f"Processing page {idx + 1}/{len(images)}...")
                    
                    # Resize image to 40% to save memory
                    new_width = max(int(image.width * 0.4), 400)
                    new_height = int(image.height * 0.4)
                    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Convert PIL Image to numpy array for EasyOCR
                    img_array = np.array(resized_image)
                    
                    # Perform OCR
                    results = reader.readtext(img_array, detail=0, paragraph=False)
                    
                    # Combine results
                    page_text = "\n".join(results) if results else "[No text detected]"
                    extracted_text += f"\n--- Page {idx + 1} ---\n{page_text}\n"
                    
                    # Explicit memory cleanup
                    del resized_image
                    del img_array
                    del image
                    gc.collect()
                    
                except Exception as page_error:
                    logger.warning(f"Error processing page {idx + 1}: {str(page_error)}")
                    extracted_text += f"\n--- Page {idx + 1} ---\n[Error processing page]\n"
                    gc.collect()
                    continue
            
            logger.info("Text extraction completed")
            return extracted_text.strip()
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            raise Exception(f"Error extracting text from images: {str(e)}")
    
    @staticmethod
    def save_uploaded_file(file, upload_folder):
        """Save uploaded file and return path"""
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        file_path = os.path.join(upload_folder, file.filename)
        file.save(file_path)
        return file_path
