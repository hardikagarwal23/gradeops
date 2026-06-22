# core/grader_graph.py
import os
import json
import cv2
import asyncio
import numpy as np
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from PIL import Image
from pdf2image import convert_from_path
from langgraph.graph import StateGraph, END
from core.state import StudentGradingState
from core.database import transcripts_collection, grades_collection
from core.batch_processor import start_unlimited_processing_worker # Your worker file
from config import POPPLER_PATH, IS_WINDOWS

client = genai.Client()

# -----------------------------------------------------------------
# 📋 STRUCTURED OUTPUT SCHEMA CONTRACTS FOR GEMINI REASONER
# -----------------------------------------------------------------
class QuestionEvaluation(BaseModel):
    question_number: str = Field(description="The exact identifier matching the rubric e.g., '1_i', '3_iv'")
    max_marks: float = Field(description="The total possible marks specified for this question block")
    marks_awarded: float = Field(description="The score assigned to the student's answer.")
    exact_evaluated_text_segment: str = Field(description="The exact literal text segment pulled verbatim from the student's script.")
    deduction_reason: Optional[str] = Field(None, description="Clear, concise reason why marks were deducted.")
    feedback: Optional[str] = Field("Answer transcript missing.", description="Targeted academic feedback.")

class FinalGradingPayload(BaseModel):
    subject: Optional[str] = "English Language and Literature"
    total_max_marks: float = Field(description="Sum total of all max_marks evaluated")
    total_marks_awarded: float = Field(description="Sum total of all marks_awarded")
    question_breakdown: List[QuestionEvaluation] = Field(description="The full array of graded questions")


# -----------------------------------------------------------------
# 🗂️ NODE 1: NATIVE ASYNC COMPILER & TEXT EXTRACTION NODE (DEADLOCK FREE)
# -----------------------------------------------------------------
# 🌟 CHANGED TO ASYNC DEF TO PREVENT THREAD DEADLOCKS
async def compile_transcript_node(state: StudentGradingState) -> dict:
    student_id = state["student_id"]
    batch_id = state["batch_id"]
    
    print(f"\n🗂️ [Compiler] Slicing & optimizing PDF layers for Student ID: {student_id}...")
    student_dir = os.path.join("uploaded_exams", batch_id, student_id)
    pdf_matches = [f for f in os.listdir(student_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_matches:
        print(f"❌ Error: Master PDF target missing in portfolio directory: '{student_dir}'")
        return {"compiled_master_transcript": "[EMPTY]"}
        
    absolute_pdf_path = os.path.join(student_dir, pdf_matches[0])
    
    try:
        # --- 1. RUN OPTIMIZED IMAGE SLICING MATRIX ---
        convert_kwargs = {"dpi": 200}
        if IS_WINDOWS:
            convert_kwargs["poppler_path"] = POPPLER_PATH

        # Since convert_from_path reads files from disk, wrap it in an async thread execution worker pool
        pages = await asyncio.to_thread(convert_from_path, absolute_pdf_path, **convert_kwargs)
        print(f"📸 Extracted {len(pages)} raw page layers from PDF.")
        
        # --- 2. PRE-STAGE METADATA IN MONGODB (PENDING STATUS) ---
        for index, page in enumerate(pages):
            page_num = index + 1
            img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

            h, w = img.shape[:2]
            max_dim = 1600
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            out_path = os.path.join(student_dir, f"page_{page_num}.jpg")
            await asyncio.to_thread(cv2.imwrite, out_path, gray)

            # Insert PENDING status trace lines into database indices
            page_doc = {
                "_id": f"{batch_id}_{student_id}_PAGE_{page_num}",
                "batch_id": batch_id,
                "student_id": student_id,
                "page_number": page_num,
                "file_path": out_path,
                "extracted_text": "Transcribing via Kaggle GPU pipeline cluster...",
                "status": "PENDING"
            }
            transcripts_collection.update_one({"_id": page_doc["_id"]}, {"$set": page_doc}, upsert=True)

        # --- 3. AWAIT UNMETERED KAGGLE ASYNC WORKER POOL LOOP ---
        print(f"🏎️ Booting background queue stream worker over Ngrok tunnel...")
        
        # 🚀 THE CRITICAL FIX: Clean native await. No thread blockages, no hanging variables!
        await start_unlimited_processing_worker(batch_id, student_id)

        # --- 4. ASSEMBLE PROCESSED TRANSCRIPTS OUT OF ATLAS ---
        cursor = transcripts_collection.find(
            {"batch_id": batch_id, "student_id": student_id, "status": "PROCESSED"}
        ).sort("page_number", 1)
        
        student_pages_text = [doc["extracted_text"] for doc in cursor]
        
        if not student_pages_text:
            print(f"⚠️ Warning: Scoped transcripts could not be recovered out of database pools.")
            return {"compiled_master_transcript": "[EMPTY]"}

        compiled_transcript = "\n\n--- NEXT PAGE ---\n\n".join(student_pages_text)
        return {"compiled_master_transcript": compiled_transcript}

    except Exception as e:
        print(f"❌ Internal Pipeline Processing Engine Failure: {str(e)}")
        return {"compiled_master_transcript": "[EMPTY]"}


# -----------------------------------------------------------------
# ⚖️ NODE 2: SCHEMA-ENFORCED REASONING GRADER NODE (ASYNC CAPABLE)
# -----------------------------------------------------------------
# 🌟 CHANGED TO ASYNC DEF FOR UNIFIED TIMING AND ASYNC FLOWS
async def evaluate_with_rubric_node(state: StudentGradingState) -> dict:
    print(f"⚖️ [Grader] Evaluating {state['student_id']} via Schema-Enforced Output Matrices...")
    
    if state["compiled_master_transcript"] == "[EMPTY]":
        fallback_empty = {
            "subject": state["rubric_data"].get("subject", "Unknown Subject"),
            "total_max_marks": 0.0,
            "total_marks_awarded": 0.0,
            "question_breakdown": []
        }
        return {"evaluation_breakdown": fallback_empty}

    rubric_rules = state["rubric_data"].get("questions", [])

    system_instruction = (
        "You are an expert board examiner. Grade the student's text transcript objectively against the official rubric criteria.\n\n"
        "Guidelines:\n"
        "1. Calculate total_max_marks and total_marks_awarded exactly by summing up your itemized scores.\n"
        "2. CRITICAL: For each question, extract and isolate the exact sentences or phrases from the student's transcript "
        "that correspond to their answer, and populate it into 'exact_evaluated_text_segment' completely verbatim."
    )
    
    try:
        # Wrap the synchronous genai SDK network call inside an async thread block execution wrapper pool
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.5-flash-lite',
            contents=[
                f"OFFICIAL RUBRIC CRITERIA SCHEMA:\n{json.dumps(rubric_rules, indent=2)}\n\n",
                f"STUDENT COMPARED TRANSCRIPT:\n{state['compiled_master_transcript']}"
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                max_output_tokens=8192, 
                response_mime_type="application/json",
                response_schema=FinalGradingPayload, 
            )
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        parsed_json = json.loads(raw_text)
        return {"evaluation_breakdown": parsed_json}

    except Exception as e:
        print(f"❌ Exception encountered during structured grading matrix synthesis: {str(e)}")
        fallback_error = {
            "subject": state["rubric_data"].get("subject", "Class X Examination"),
            "total_max_marks": 50.0,
            "total_marks_awarded": 0.0,
            "question_breakdown": [
                {
                    "question_number": "ERROR_HALT",
                    "max_marks": 0.0,
                    "marks_awarded": 0.0,
                    "exact_evaluated_text_segment": "Pipeline tracking fatal exception exception.",
                    "deduction_reason": f"Pipeline parsing exception: {str(e)}",
                    "feedback": "Please re-trigger this evaluation manual override row cell choice link directly."
                }
            ]
        }
        return {"evaluation_breakdown": fallback_error}

# -----------------------------------------------------------------
# 🏁 BUILD THE WORKFLOW GRAPH MATRIX (NATIVELY ASYNC NOW)
# -----------------------------------------------------------------
workflow = StateGraph(StudentGradingState)
workflow.add_node("compiler", compile_transcript_node)
workflow.add_node("grader", evaluate_with_rubric_node)

workflow.set_entry_point("compiler")
workflow.add_edge("compiler", "grader")
workflow.add_edge("grader", END)

# Compiles completely as an async pipeline runner out of the box
grading_pipeline = workflow.compile()
print("🟢 LangGraph Orchestration engine initialized natively as ASYNC!")
