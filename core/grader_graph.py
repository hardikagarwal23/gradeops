# core/grader_graph.py
import os
import json
import time
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from langgraph.graph import StateGraph, END
from core.state import StudentGradingState
from core.database import transcripts_collection

client = genai.Client()

# -----------------------------------------------------------------
# 📋 STEP 1: DEFINE FAULT-TOLERANT PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# -----------------------------------------------------------------
class QuestionEvaluation(BaseModel):
    question_number: str = Field(
        description="The exact identifier matching the rubric e.g., '1_i', '3_iv', or '11_ii'"
    )
    max_marks: float = Field(
        description="The total possible marks specified for this question block in the rubric"
    )
    marks_awarded: float = Field(
        description="The score assigned to the student's answer. Deduct strictly based on criteria. Award 0.0 if the answer transcript track is missing."
    )
    # 🌟 NEW FIELD FOR OPTION 2 ARCHITECTURE
    exact_evaluated_text_segment: str = Field(
        description=(
            "The exact literal text segment or snippet pulled verbatim from the student's compared transcript "
            "that contains their answer for this specific question. If the student did not attempt it or the "
            "transcript is missing, return 'Answer segment not found.'"
        )
    )
    deduction_reason: Optional[str] = Field(
        None, 
        description="Clear, concise reason why marks were deducted. Must be null/None if full marks are achieved or if the question wasn't attempted."
    )
    feedback: Optional[str] = Field(
        "Answer transcript missing or unreadable.",
        description="Targeted academic feedback explaining what was correct or missing from the student's answer."
    )

class FinalGradingPayload(BaseModel):
    subject: Optional[str] = "English Language and Literature"
    total_max_marks: float = Field(description="Sum total of all max_marks from the rubric questions evaluated")
    total_marks_awarded: float = Field(description="Sum total of all marks_awarded across the question evaluations")
    question_breakdown: List[QuestionEvaluation] = Field(description="The full array of graded questions")


# -----------------------------------------------------------------
# 🗂️ NODE 1: COMPILE TRANSCRIPT NODE
# -----------------------------------------------------------------
def compile_transcript_node(state: StudentGradingState) -> dict:
    print(f"\n🗂️ [Compiler] Compiling transcripts from MongoDB for student: {state['student_id']}...")
    
    cursor = transcripts_collection.find(
        {"batch_id": state["batch_id"], "student_id": state["student_id"], "status": "PROCESSED"}
    ).sort("page_num", 1)  # Using calibrated 'page_num' parameter tracking
    
    student_pages = [doc["extracted_text"] for doc in cursor]
    
    if not student_pages:
        return {"compiled_master_transcript": "[EMPTY]"}
        
    return {"compiled_master_transcript": "\n\n--- PAGE BREAK ---\n\n".join(student_pages)}


# -----------------------------------------------------------------
# ⚖️ NODE 2: STRUCTURED GRADER NODE
# -----------------------------------------------------------------
def evaluate_with_rubric_node(state: StudentGradingState) -> dict:
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

    # 🌟 UPDATED INSTRUCTIONS FOR DYNAMIC EVALUATION SEGMENTATION
    system_instruction = (
        "You are an expert board examiner. Grade the student's text transcript objectively against the official rubric criteria.\n\n"
        "Guidelines:\n"
        "1. For comprehension and descriptive items, verify key concepts and keyword combinations thoroughly.\n"
        "2. For grammatical, punctuation, or reordering questions, enforce strict structural accuracy.\n"
        "3. Evaluate the text completely across all pages. If a page was skipped or has empty text due to pipeline drops, award 0.0 marks for those corresponding questions.\n"
        "4. Calculate total_max_marks and total_marks_awarded exactly by summing up your itemized scores.\n"
        "5. CRITICAL: For each question, extract and isolate the exact sentences or phrases from the student's transcript "
        "that correspond to their answer, and populate it into 'exact_evaluated_text_segment' completely verbatim."
    )
    
    print("⏳ Applying 15-second pacing delay for Gemini Free Tier...")
    time.sleep(15)
    
    try:
        response = client.models.generate_content(
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
            "total_max_marks": 80.0,
            "total_marks_awarded": 0.0,
            "question_breakdown": [
                {
                    "question_number": "ERROR_HALT",
                    "max_marks": 0.0,
                    "marks_awarded": 0.0,
                    "exact_evaluated_text_segment": "Pipeline error occurred during parsing.",
                    "deduction_reason": f"Pipeline parsing exception: {str(e)}",
                    "feedback": "Please re-trigger this evaluation batch window run manually."
                }
            ]
        }
        return {"evaluation_breakdown": fallback_error}

# -----------------------------------------------------------------
# 🏁 BUILD THE WORKFLOW GRAPH MATRIX
# -----------------------------------------------------------------
workflow = StateGraph(StudentGradingState)
workflow.add_node("compiler", compile_transcript_node)
workflow.add_node("grader", evaluate_with_rubric_node)

workflow.set_entry_point("compiler")
workflow.add_edge("compiler", "grader")
workflow.add_edge("grader", END)

grading_pipeline = workflow.compile()
print("🟢 LangGraph Orchestration engine initialized with Agentic Text Isolation Support!")


