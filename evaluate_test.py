import os
import sys
from dotenv import load_dotenv

# Ensure we're running from ai-examiner root
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
load_dotenv('backend/.env')

from backend.utils.gemini_service import GeminiService

gemini_srv = GeminiService(os.environ.get("GEMINI_API_KEY"))

with open('model_text.txt', 'r', encoding='utf-8') as f:
    model_text = f.read()

with open('student_text.txt', 'r', encoding='utf-8') as f:
    student_text = f.read()

print("Evaluating using Gemini directly...")
try:
    evaluation = gemini_srv.evaluate_answer(student_text, model_text, 100)
    print("\n--- FINAL JSON RESULT ---")
    print(evaluation)
except Exception as e:
    print(f"Failed evaluation: {e}")
