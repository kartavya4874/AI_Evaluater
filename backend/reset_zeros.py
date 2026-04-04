import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/ai_examiner')
DB_NAME = os.getenv('DB_NAME', 'ai_examiner')

def clear_zero_evaluations():
    print("Connecting to MongoDB...")
    try:
        if "mongodb+srv" in MONGO_URI:
            client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        else:
            client = MongoClient(MONGO_URI)
            
        db = client[DB_NAME]
        evaluations_collection = db['evaluations']
        
        # Find how many we are deleting
        count = evaluations_collection.count_documents({"marks": 0, "batch_mode": True})
        
        if count == 0:
            print("No 0-mark batch evaluations found. Nothing to delete.")
            return

        print(f"Found {count} batch evaluations with 0 marks (likely due to the previous 429 API failures).")
        
        # Delete them
        result = evaluations_collection.delete_many({"marks": 0, "batch_mode": True})
        
        print(f"✅ Successfully deleted {result.deleted_count} failed evaluations.")
        print("You can now safely restart the batch processing. The system will rescan those exact students!")

    except Exception as e:
        print(f"❌ Error talking to MongoDB: {e}")

if __name__ == "__main__":
    clear_zero_evaluations()
