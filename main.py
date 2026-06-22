import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from core.database import grades_collection, transcripts_collection
from core.grader_graph import grading_pipeline

load_dotenv()

async def main():
    # 🌟 DYNAMIC CLI FALLBACK CHECKS:
    # sys.argv[1] reads the batch name
    target_batch = sys.argv[1] if len(sys.argv) > 1 else "final_2026"
    
    # 🛠️ AUTOMATED FALLBACK: If a custom rubric path isn't provided, infer it from the batch code dynamically
    rubric_file_path = sys.argv[2] if len(sys.argv) > 2 else f"rubric_{target_batch}.json"
    
    # Construct the directory dynamically using your parsed tracking string
    upload_root_dir = f"./uploaded_exams/{target_batch}/"
    
    print("====================================================")
    print("⚖️ GradeOps Bulk Folder Processing Engine Active")
    print(f"📦 Active Target Batch: {target_batch}")
    print(f"📖 Using Rubric Reference File: {rubric_file_path}")
    print("====================================================")
    
    # 1. LOAD THE MASTER RUBRIC CRITERIA
    if not os.path.exists(rubric_file_path):
        print(f"❌ Error: Master rubric missing at path: '{rubric_file_path}'")
        return
        
    with open(rubric_file_path, "r", encoding="utf-8") as f:
        rubric_doc = json.load(f)
    print(f"📁 Loaded Rubric Matrix: {rubric_doc.get('subject')}")

    # 2. DISCOVER STUDENT FOLDERS SYSTEMATICALLY
    if not os.path.exists(upload_root_dir):
        print(f"❌ Error: Upload target folder path directory not found: '{upload_root_dir}'")
        return
        
    # Scan the subdirectories representing each roll number/student id portfolio entry
    all_items = os.listdir(upload_root_dir)
    student_folders = [item for item in all_items if os.path.isdir(os.path.join(upload_root_dir, item))]
    
    print(f"📂 Detected {len(student_folders)} unique student portfolio directories.")
    print("----------------------------------------------------")

    # 3. THE BATCH LOOP: PROCESSING INDIVIDUAL STUDENT PORTFOLIOS
    for current_student_id in student_folders:
        student_subfolder_path = os.path.join(upload_root_dir, current_student_id)
        
        # Look for the PDF copy inside the student's subfolder
        student_files = os.listdir(student_subfolder_path)
        pdf_matches = [f for f in student_files if f.lower().endswith('.pdf')]
        
        if not pdf_matches:
            print(f"⚠️ Warning: No target PDF located inside directory tracker: '{current_student_id}'. Skipping.")
            continue
            
        target_pdf_name = pdf_matches[0]
        absolute_pdf_path = os.path.join(student_subfolder_path, target_pdf_name)
        
        print(f"\n🚀 Starting Automation Chain for Student ID: '{current_student_id}'...")
        print(f"📄 Processing file source path: {absolute_pdf_path}")
        
        # Initialize LangGraph pipeline context memory configuration dictionary
        initial_graph_state = {
            "batch_id": target_batch,
            "student_id": current_student_id,
            "pdf_path": absolute_pdf_path, # Provide your pipeline the precise file system location
            "rubric_data": rubric_doc,
            "compiled_master_transcript": "",
            "evaluation_breakdown": {}
        }
        
        try:
            # Invoke the LangGraph multi-agent network execution natively as an async coroutine
            final_output_state = await grading_pipeline.ainvoke(initial_graph_state)
            eval_data = final_output_state.get("evaluation_breakdown", {})
            
            if not eval_data or "question_breakdown" not in eval_data:
                print(f"⚠️ Warning: Network generation skipped or failed for student: {current_student_id}")
                continue

            # Build structural grading payload profile mapping definitions
            grade_record = {
                "_id": f"{target_batch}_{current_student_id}_GRADE",
                "batch_id": target_batch,
                "student_id": current_student_id,
                "subject": eval_data.get("subject", rubric_doc.get("subject")),
                "total_max_marks": eval_data.get("total_max_marks", 50.0), # Default fallback tracking to 50 marks matrix
                "total_marks_awarded": eval_data.get("total_marks_awarded", 0.0),
                # 🌟 FIXED: Clean, non-deprecated timezone aware UTC tracker syntax
                "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "question_breakdown": eval_data.get("question_breakdown", []),
                "status": "COMPLETED"
            }
            
            # Atomic database upsert sync 
            grades_collection.update_one(
                {"_id": grade_record["_id"]}, 
                {"$set": grade_record}, 
                upsert=True
            )
            print(f"✅ Successfully saved report metrics for '{current_student_id}' in Atlas!")
            print(f"📊 Final Score: {grade_record['total_marks_awarded']} / {grade_record['total_max_marks']}")
            
        except Exception as student_error:
            print(f"❌ Critical failure processing student template record '{current_student_id}': {str(student_error)}")
            continue # Keep the batch loop running even if one student's file fails
            
    print("\n====================================================")
    print("🏁 BULK BATCH FOLDER PROCESSING COMPLETED")
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(main())
