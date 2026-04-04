import os
import sys
from dotenv import load_dotenv

# Ensure we're running from ai-examiner root
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
load_dotenv('backend/.env')

from backend.utils.pdf_processor import PDFProcessor
from backend.utils.gemini_service import GeminiService

pdf_proc = PDFProcessor()
gemini_srv = GeminiService(os.environ.get("GEMINI_API_KEY"))

model_pdf = r"uploads\Model answer.pdf"
student_pdf = r"uploads\FS3401_2201304002.pdf"

print("Extracting model answer...")
try:
    model_text = pdf_proc.extract_text_from_pdf(model_pdf)
    with open('model_text.txt', 'w', encoding='utf-8') as f:
        f.write(model_text)
    print("Model answer extracted.")
except Exception as e:
    print(f"Failed model: {e}")

print("Extracting student answer...")
try:
    student_text = pdf_proc.extract_text_from_pdf(student_pdf)
    if len(student_text.strip()) < 100:
        print("Using Gemini Vision for student answer...")
        images = pdf_proc.convert_pdf_to_images(student_pdf, max_pages=15) # Maybe 15 pages instead of 5?
        student_text = pdf_proc.extract_text_from_images_via_gemini(images, gemini_srv)
    with open('student_text.txt', 'w', encoding='utf-8') as f:
        f.write(student_text)
    print("Student answer extracted.")
except Exception as e:
    print(f"Failed student: {e}")
