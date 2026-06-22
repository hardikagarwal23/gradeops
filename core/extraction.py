import asyncio
import os
from core.database import transcripts_collection

# Asynchronous worker function processing an isolated single page image
async def extract_text_from_single_page(page_image_path, page_num, student_id, batch_id):
    try:
        # 🔗 PIPELINE HOOK: Insert your specific VLM/Gemini vision request call here
        # loop = asyncio.get_event_loop()
        # response = await loop.run_in_executor(None, call_gemini_vision_api, page_image_path)
        
        # Fallback text placeholder for testing
        extracted_text_result = f"[Extracted Transcript Text Sample for Page {page_num}]"
        
        page_doc = {
            "_id": f"{batch_id}_{student_id}_PAGE_{page_num}",
            "batch_id": batch_id,
            "student_id": student_id,
            "page_number": page_num,
            "file_path": page_image_path,
            "extracted_text": extracted_text_result,
            "status": "PROCESSED"
        }
        
        # Write live to MongoDB Atlas so the UI can render it immediately page-by-page
        transcripts_collection.update_one(
            {"_id": page_doc["_id"]},
            {"$set": page_doc},
            upsert=True
        )
        return extracted_text_result
        
    except Exception as e:
        print(f"❌ Error on Page {page_num}: {str(e)}")
        return ""

async def process_student_text_extraction_parallel(student_id, batch_id, page_image_paths):
    """Fires all page images to the VLM at the exact same time."""
    tasks = []
    # Loop over all individual page paths discovered after splitting the PDF
    for idx, img_path in enumerate(page_image_paths):
        task = extract_text_from_single_page(img_path, page_num=idx+1, student_id=student_id, batch_id=batch_id)
        tasks.append(task)
        
    # Execution barrier: Runs all pages simultaneously!
    all_extracted_pages_text = await asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
    
    # Stitch the sheets together seamlessly for the LangGraph grading agent context pool
    compiled_master_transcript = "\n\n--- NEXT PAGE ---\n\n".join(all_extracted_pages_text)
    return compiled_master_transcript
