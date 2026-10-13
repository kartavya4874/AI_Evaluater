import os
import certifi
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/ai_examiner')
DB_NAME = os.getenv('DB_NAME', 'ai_examiner')

def export_evaluations_to_excel():
    print("Connecting to MongoDB...")
    try:
        if "mongodb+srv" in MONGO_URI:
            client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        else:
            client = MongoClient(MONGO_URI)
            
        db = client[DB_NAME]
        evaluations_collection = db['evaluations']
        
        # Fetch all batch evaluations (ignoring individual manual grades if any)
        print("Fetching data from the 'evaluations' collection...")
        evaluations = list(evaluations_collection.find({"batch_mode": True}))
        
        if not evaluations:
            print("No batch evaluations found in the database.")
            return

        print(f"Loaded {len(evaluations)} total evaluations. Processing data...")
        
        # Structure the data
        data = []
        for eval in evaluations:
            data.append({
                "Course Code": eval.get("course_code", "Unknown"),
                "Roll Number": eval.get("roll_number", "Unknown"),
                "Marks Awarded": eval.get("marks", 0),
                "Max Marks": eval.get("max_marks", 100),
                "Percentage (%)": eval.get("percentage", 0),
                "Grade": eval.get("grade", "N/A"),
                "Needs Review (Error)": "Yes" if eval.get("status") == "error" or eval.get("needs_review") else "No"
            })
            
        df = pd.DataFrame(data)
        
        # Create output directory
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(output_dir, f"University_Results_Export_{timestamp}.xlsx")
        
        print(f"Creating Excel file: {output_file}")
        
        # Write to Excel, with a separate sheet for each course code
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Group by Course Code
            course_groups = df.groupby("Course Code")
            
            for course_code, group in course_groups:
                # Sort by Roll number for sequential listing
                group_sorted = group.sort_values(by="Roll Number")
                # Drop the "Course Code" column since it's the sheet name
                group_sorted = group_sorted.drop(columns=["Course Code"])
                
                # Write to sheet
                sheet_name = str(course_code)[:31] # Excel limits sheet names to 31 chars
                group_sorted.to_excel(writer, sheet_name=sheet_name, index=False)
                
            # Create a master Summary sheet at the beginning
            summary_data = []
            for course_code, group in course_groups:
                summary_data.append({
                    "Course Code": course_code,
                    "Total Students Processed": len(group),
                    "Average Marks": round(group["Marks Awarded"].mean(), 2),
                    "Failed / Needs Review": len(group[group["Needs Review (Error)"] == "Yes"])
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Master Summary", index=False)
            
        print(f"✅ Success! Excel sheet generated successfully at: {output_file}")
        print("You can now open it in Microsoft Excel.")

    except Exception as e:
        print(f"❌ Error extracting data: {e}")
        print("Tip: Make sure you have installed 'pandas' and 'openpyxl'. Run: pip install pandas openpyxl")

if __name__ == "__main__":
    export_evaluations_to_excel()
