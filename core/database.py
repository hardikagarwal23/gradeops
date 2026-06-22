import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load your secure environment strings (.env)
load_dotenv()

# Fallback to local connection string if you haven't specified your Mongo Atlas URI yet
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

# Establish direct socket client connection pool to your Mongo Cluster
client = MongoClient(MONGO_URI)

# Select/Create your primary backend database name
db = client["gradeops_db"]

# Map your specific workflow collections
transcripts_collection = db["page_transcripts"]
grades_collection = db["final_grades"]
rubrics_collection = db["rubrics"]

def queue_page_asset(page_id: str, batch_id: str, student_id: str, page_num: int, file_path: str):
    """
    Upserts an optimized page metadata frame directly into your 
    central MongoDB tracking collection.
    """
    query = {"_id": page_id}
    update_data = {
        "$setOnInsert": {
            "batch_id": batch_id,
            "student_id": student_id,
            "page_number": page_num,
            "file_path": file_path,
            "status": "PENDING",  # State flags: PENDING, PROCESSING, PROCESSED, FAILED
            "extracted_text": ""
        }
    }
    
    # upsert=True prevents duplicate key entries if the pipeline restarts midway
    transcripts_collection.update_one(query, update_data, upsert=True)
    print(f"💾 Page enqueued in MongoDB: {page_id}")
