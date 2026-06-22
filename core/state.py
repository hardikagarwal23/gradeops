# core/state.py
from typing import List, Dict, TypedDict

class StudentGradingState(TypedDict):
    """
    The shared memory canvas passed sequentially between our 
    LangGraph evaluation and formatting agents.
    """
    batch_id: str                   # Tracks the overall semester batch
    student_id: str                 # Isolates the specific student being graded
    solution_text: str              # Reference text parsed from professor's solution key
    rubric_data: Dict               # Strict point breakdown rules schema
    raw_page_transcripts: List[str] # Direct markdown string arrays from Kaggle
    compiled_master_transcript: str # Stitched chronological text from Node 1
    evaluation_breakdown: Dict      # Intermediate score calculations
    final_feedback_markdown: str    # The finished report card string from Gemini
