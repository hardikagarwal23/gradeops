# core/batch_processor.py
import asyncio
from core.database import transcripts_collection
from core.vlm_handler import extract_handwriting_with_retry  # Supposing this wraps your requests post call

async def start_unlimited_processing_worker(batch_id: str):
    """
    Background worker loop that coordinates directly with your MongoDB cluster,
    streaming document frames to Kaggle at maximum hardware processing speeds.
    """
    print(f"\n🏎️ Fast-track MongoDB queue worker active for Batch: {batch_id}")
    
    while True:
        # 1. Atomically find one pending page and lock it to 'PROCESSING' state.
        # find_one_and_update prevents multiple async worker threads from picking up the same page asset.
        page_row = transcripts_collection.find_one_and_update(
            {"batch_id": batch_id, "status": "PENDING"},
            {"$set": {"status": "PROCESSING"}},
            sort=[("student_id", 1), ("page_number", 1)]
        )
        
        # 2. If no documents return with a PENDING status, terminate the queue loop.
        if not page_row:
            print(f"🎉 Success: All handwritten sheets for Batch '{batch_id}' have been processed in MongoDB!")
            break
            
        page_id = page_row["_id"]
        student_id = page_row["student_id"]
        page_num = page_row["page_number"]
        file_path = page_row["file_path"]
        
        print(f"\n📖 Active Target -> Student: {student_id} | Page Frame: {page_num}")
        
        try:
            # 3. Dispatch the network execution call to your remote Kaggle VLM thread pool.
            # asyncio.to_thread prevents the synchronous 'requests' code from blocking the event loop.
            extracted_markdown = await asyncio.to_thread(extract_handwriting_with_retry, file_path)
            
            # 4. Commit clean markdown text to MongoDB and flag the frame as complete.
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
            # Roll back status to FAILED so it can be re-queued or audited
            transcripts_collection.update_one(
                {"_id": page_id},
                {"$set": {"status": "FAILED"}}
            )
            
        # 5. Crucial: Fast-track pacing index.
        # Since Kaggle is unmetered, we drop the old 4.5s delay. A 0.1s gap lets the database pool breathe.
        await asyncio.sleep(0.1)