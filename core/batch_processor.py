import asyncio
from core.database import transcripts_collection
from core.vlm_handler import extract_handwriting_with_retry 

async def start_unlimited_processing_worker(batch_id: str, student_id: str):
    print(f"\n🏎️ Fast-track MongoDB queue worker active for Student: {student_id}")
    
    while True:
        # 🤝 SCOPED LOOKUP: Only fetch PENDING pages for this specific student
        page_row = transcripts_collection.find_one_and_update(
            {"batch_id": batch_id, "student_id": student_id, "status": "PENDING"},
            {"$set": {"status": "PROCESSING"}},
            sort=[("page_number", 1)]
        )
        
        # If this student has no more PENDING pages, exit the loop cleanly!
        if not page_row:
            print(f"🎉 Success: All pages for Student '{student_id}' have been processed!")
            break
            
        page_id = page_row["_id"]
        page_num = page_row["page_number"]
        file_path = page_row["file_path"]
        
        print(f"📖 Active Target -> Page Frame: {page_num}")
        
        try:
            extracted_markdown = await asyncio.to_thread(extract_handwriting_with_retry, file_path)
            
            transcripts_collection.update_one(
                {"_id": page_id},
                {
                    "$set": {
                        "status": "PROCESSED", 
                        "extracted_text": extracted_markdown.strip()
                    }
                }
            )
            print(f"✅ Document state updated to PROCESSED for key: {page_id}")
            
        except Exception as e:
            print(f"❌ Transcription execution failed for frame {page_id}: {str(e)}")
            transcripts_collection.update_one(
                {"_id": page_id},
                {"$set": {"status": "FAILED"}}
            )
            
        await asyncio.sleep(0.1)
