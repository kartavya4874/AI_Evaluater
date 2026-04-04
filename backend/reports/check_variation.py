import pandas as pd

try:
    df = pd.read_excel('c:\\Users\\karta\\EVA\\ai-examiner\\backend\\reports\\Marks Variation  .xlsx')
    output = df.head(100).to_string()
    with open('c:\\Users\\karta\\EVA\\ai-examiner\\backend\\reports\\variation_preview.txt', 'w', encoding='utf-8') as f:
        f.write(output)
    print("Success")
except Exception as e:
    with open('c:\\Users\\karta\\EVA\\ai-examiner\\backend\\reports\\variation_preview.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))
    print(f"Failed: {e}")
