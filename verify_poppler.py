import os
import platform
from dotenv import load_dotenv
import subprocess

# Load environment from backend/.env
load_dotenv('backend/.env')

poppler_path = os.getenv('POPPLER_PATH')
print(f"OS: {platform.system()}")
print(f"Poppler Path from .env: {poppler_path}")

if poppler_path and os.path.exists(poppler_path):
    print("Poppler path exists.")
    pdftoppm_path = os.path.join(poppler_path, 'pdftoppm.exe')
    if os.path.exists(pdftoppm_path):
        print(f"pdftoppm.exe found at: {pdftoppm_path}")
        try:
            result = subprocess.run([pdftoppm_path, '-v'], capture_output=True, text=True)
            print("Poppler version info:")
            print(result.stderr)
            print("Verification SUCCESSFUL")
        except Exception as e:
            print(f"Error running pdftoppm: {e}")
    else:
        print(f"pdftoppm.exe NOT found at {pdftoppm_path}")
else:
    print("Poppler path NOT found or does not exist.")
