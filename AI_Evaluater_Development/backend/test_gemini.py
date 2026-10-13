import google.generativeai as genai
from config import Config

print("Testing Gemini API...")
print(f"API Key (first 10 chars): {Config.GEMINI_API_KEY[:10]}...")

# Configure Gemini
genai.configure(api_key=Config.GEMINI_API_KEY)

# List available models
print("\n=== Available Models ===")
try:
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"- {model.name}")
except Exception as e:
    print(f"Error listing models: {e}")

# Test different models
models_to_test = [
    'gemini-pro',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-3-flash-preview',
    'models/gemini-pro',
    'models/gemini-1.5-flash'
]

print("\n=== Testing Models ===")
for model_name in models_to_test:
    try:
        print(f"\nTesting: {model_name}")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say 'Hello! I am working.' in one sentence.")
        print(f"✓ SUCCESS: {response.text}")
        break  # Stop after first successful model
    except Exception as e:
        print(f"✗ FAILED: {str(e)[:100]}")

print("\n=== Test Complete ===")
