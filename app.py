# app.py
import streamlit as st
import os
import json
from core.database import transcripts_collection, grades_collection
from core.plagiarism_checker import check_classroom_plagiarism

# 1. GLOBAL SYSTEM CONFIGURATION
st.set_page_config(page_title="GradeOps AI Portal", page_icon="⚖️", layout="wide")

if "user_role" not in st.session_state:
    st.session_state["user_role"] = "Instructor"

# Inject Global CSS styling setups for the Floating Bottom Panel Drawer Architecture
st.markdown("""
    <style>
    .stMainBlockContainer {
        padding-bottom: 100px !important; 
    }
    div[data-testid="stPopoverBody"] {
        max-width: 360px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 2. SIDEBAR NAVIGATION & ACCESS CONTROL (RBAC)
with st.sidebar:
    st.title("⚖️ GradeOps Control Panel")
    st.markdown("---")
    st.session_state["user_role"] = st.selectbox(
        "Active Session Profile Role", 
        ["Instructor", "Teaching Assistant (TA)"]
    )
    st.markdown("---")
    workspace = st.radio(
        "Select Active Workspace Engine",
        ["📤 Bulk Exam Ingestion", "⚖️ High-Throughput TA Review", "🚨 Plagiarism Audit Analytics"]
    )
    st.markdown("---")
    st.caption("GradeOps Production Core v1.0.0 (MERN-AI Engine Pipeline)")

# =========================================================================
# WORKSPACE A: BULK EXAM INGESTION TERMINAL (DYNAMIC USER INPUTS)
# =========================================================================
if workspace == "📤 Bulk Exam Ingestion":
    st.title("📤 Bulk Examination Ingestion Terminal")
    st.markdown("---")
    
    if st.session_state["user_role"] != "Instructor":
        st.error("⛔ Access Denied: Ingestion setup configurations are strictly restricted to Instructors.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("1. Setup Exam Context Matrix")
            # 🌟 DYNAMIC SELECTION: Taken dynamically from user inputs
            target_batch = st.text_input("Target Batch Identifier Code", "final_2026")
            subject = st.text_input("Subject Classification Field", "English Language and Literature")
            rubric_file = st.file_uploader("Upload Reference Rubric JSON", type=["json"])
        with col2:
            st.subheader("2. Bulk Folder Contents Ingestion")
            st.info("""
                💡 **Batch Folder Onboarding:**
                1. Open your target exam folder on your computer.
                2. Press **Ctrl+A** or **Cmd+A** to highlight ALL student answer copies inside.
                3. Drag and drop them together into the box below. Filenames must be `ROLL_NUMBER.pdf`.
            """)
            
            # Setting accept_multiple_files=True handles multi-file bulk uploads seamlessly
            exam_files = st.file_uploader(
                "Drop all student PDFs from your folder here", 
                type=["pdf"], 
                accept_multiple_files=True
            )
            
        st.markdown("---")
        if st.button("🚀 Execute Ingestion & Multi-Agent Grading Loop", type="primary"):
            if exam_files and rubric_file:
                try:
                    # Save the dynamic uploaded rubric file locally into project root workspace
                    rubric_filename = f"rubric_{target_batch}.json"
                    with open(rubric_filename, "w", encoding="utf-8") as f:
                        json.dump(json.load(rubric_file), f, indent=4)
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_students = len(exam_files)
                    
                    # Process files dynamically inside file selection streams
                    for idx, pdf_file in enumerate(exam_files):
                        student_id = pdf_file.name.split(".pdf")[0].upper().strip()
                        status_text.markdown(f"📦 **Processing Student Portfolio [{idx+1}/{total_students}]:** `{student_id}`")
                        
                        # Isolate directories cleanly by unique identifiers
                        student_dir = os.path.join("uploaded_exams", target_batch, student_id)
                        os.makedirs(student_dir, exist_ok=True)
                        
                        # Reconstruct file data stream safely to local target disk bounds
                        target_save_path = os.path.join(student_dir, pdf_file.name)
                        with open(target_save_path, "wb") as f:
                            f.write(pdf_file.getbuffer())
                        
                        progress_bar.progress((idx + 1) / total_students)
                        
                    status_text.success(f"🎉 Folder contents saved successfully! Generated environments for {total_students} students.")
                    
                    # 🌟 TRIGGER BACKGROUND GRADING LOOP PASSING CLI ARGUMENTS
                    import subprocess
                    subprocess.Popen([
                        "python", "main.py", 
                        target_batch, 
                        rubric_filename
                    ])
                    st.info("🚀 Automation engine activated in secondary background thread! Monitor your console terminal logs for completions.")
                except Exception as e:
                    st.error(f"❌ Ingestion Execution Interrupted: {str(e)}")
            else:
                st.warning("⚠️ High alert: Missing files. Ensure both rubric schema and exam copies are present.")

# =========================================================================
# WORKSPACE B: HIGH-THROUGHPUT TA REVIEW (DYNAMIC VIEWERS)
# =========================================================================
elif workspace == "⚖️ High-Throughput TA Review":
    st.title("⚖️ Human-in-the-Loop (HITL) Review Dashboard")
    st.markdown("---")
    
    target_batch = "final_2026"
    
    all_grades_cursor = grades_collection.find({"batch_id": target_batch})
    student_list = list(set([doc["student_id"] for doc in all_grades_cursor if "student_id" in doc]))
    
    if not student_list:
        st.warning(f"⚠️ No evaluated grading records found in your database for batch `{target_batch}`.")
        st.stop()
        
    active_student = st.selectbox("👤 Select Active Student Profile to Review", student_list)
    st.markdown("---")
    
    grade_record = grades_collection.find_one({"student_id": active_student, "batch_id": target_batch})
    page_cursor = transcripts_collection.find({
        "student_id": active_student, 
        "batch_id": target_batch, 
        "status": "PROCESSED"
    }).sort("page_number", 1)
    page_docs = list(page_cursor)

    if grade_record:
        st.success(f"📂 Active Portfolio: **{active_student}** | Cumulative Pipeline Score: **{grade_record.get('total_marks_awarded', 0)} / {grade_record.get('total_max_marks', 50)}**")
        
        col_pdf, col_ocr = st.columns([1, 1])
        
        with col_pdf:
            st.markdown("### 🖼️ Answer Script Source Viewer")
            available_pages = {doc.get("page_number", idx): doc.get("file_path") for idx, doc in enumerate(page_docs)}
            
            if available_pages:
                selected_page_num = st.select_slider(
                    "Navigate Script Pages:", 
                    options=sorted(available_pages.keys()),
                    value=min(available_pages.keys())
                )
                target_img_path = available_pages[selected_page_num]
                
                try:
                    normalized_path = os.path.normpath(target_img_path)
                    with open(normalized_path, "rb") as img_file:
                        st.image(img_file.read(), use_container_width=True)
                except Exception as e:
                    st.error(f"⚠️ Unable to render asset: {str(e)}")
            else:
                st.info("No file path mapping arrays located for this student record portfolio.")

        with col_ocr:
            st.markdown("### 📝 Text Transcript Audit Layer")
            st.caption("The text layout blocks auto-focus dynamically to match your page slider navigation settings.")
            
            for p_idx, page in enumerate(page_docs):
                p_num = page.get('page_number', p_idx)
                is_active_view = (p_num == selected_page_num)
                
                with st.expander(f"📄 Text Content ── Page {p_num}", expanded=is_active_view):
                    doc_id = str(page["_id"])
                    updated_text = st.text_area(
                        label="Verify / Fix OCR Extraction Typos:",
                        value=page.get("extracted_text", ""),
                        height=180,
                        key=f"text_area_{doc_id}"
                    )
                    
                    if st.button(f"💾 Commit Page {p_num} Corrections", key=f"save_page_{doc_id}", use_container_width=True):
                        transcripts_collection.update_one(
                            {"_id": page["_id"]},
                            {"$set": {"extracted_text": updated_text}}
                        )
                        st.toast(f"Page {p_num} corrections saved to Atlas storage cluster pools!")
                        st.cache_data.clear()

        # FLOATING OVERLAY PULL-UP DRAWER PANEL
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.expander("📊 🔼 CLICK TO PULL UP GRADE MARKS MATRIX DRAWER 🔼", expanded=False):
            st.markdown("### 📋 Floating Grade Card Matrix Auditing")
            st.caption("Apply manual overrides cleanly. Point mutations recalculate final parent totals atomically.")
            st.markdown("---")
            
            for idx, q_block in enumerate(grade_record.get("question_breakdown", [])):
                possible_q_keys = ["question_number", "q_num", "question", "q_no", "q"]
                q_num_raw = next((q_block[k] for k in possible_q_keys if k in q_block), f"Unknown-{idx}")
                normalized_q_num = str(q_num_raw).upper().replace(" ", "").strip()
                
                max_marks = float(q_block.get("max_marks", q_block.get("max", 1.0)))
                awarded_marks = float(q_block.get("marks_awarded", q_block.get("awarded", 0.0)))
                justification = q_block.get("feedback", q_block.get("justification", "No validation log trace."))
                
                r_col1, r_col2, r_col3, r_col4 = st.columns([1.2, 1.8, 2.0, 1.8])
                
                with r_col1:
                    st.markdown(f"**Q{q_num_raw}** `({max_marks}M)`")
                with r_col2:
                    with st.popover("🤖 Read Feedback"):
                        st.write(justification)
                with r_col3:
                    new_score = st.number_input(
                        f"Set Marks", min_value=0.0, max_value=max_marks, 
                        value=awarded_marks, step=0.5, 
                        key=f"score_input_{normalized_q_num}_{active_student}",
                        label_visibility="collapsed"
                    )
                with r_col4:
                    if st.button("✅ Override", key=f"ovr_{normalized_q_num}_{active_student}", use_container_width=True):
                        grades_collection.update_one(
                            {"student_id": active_student, "batch_id": target_batch, f"question_breakdown.{idx}.{list(q_block.keys())[0]}": q_block[list(q_block.keys())[0]]},
                            {"$set": {
                                f"question_breakdown.{idx}.marks_awarded": new_score,
                                f"question_breakdown.{idx}.awarded": new_score
                            }}
                        )
                        fresh_record = grades_collection.find_one({"student_id": active_student, "batch_id": target_batch})
                        total_sum = sum(float(item.get('marks_awarded', item.get('awarded', 0.0))) for item in fresh_record["question_breakdown"])
                        
                        grades_collection.update_one(
                            {"student_id": active_student, "batch_id": target_batch},
                            {"$set": {"total_marks_awarded": total_sum}}
                        )
                        st.toast(f"Saved custom score value: {new_score} for Q{q_num_raw}!")
                        st.rerun()
                        
                st.markdown("<div style='margin-top: -12px;'></div>", unsafe_allow_html=True)
                st.markdown("---")

# ==========================================
# WORKSPACE C: BATCH PLAGIARISM AUDIT
# ==========================================
elif workspace == "🚨 Plagiarism Audit Analytics":
    st.title("🚨 Batch Plagiarism Auditing Terminal")
    st.markdown("---")
    
    if st.session_state["user_role"] != "Instructor":
        st.error("⛔ Access Denied: Plagiarism sweeps are restricted to Instructor clearance parameters.")
    else:
        target_batch = st.text_input("Active Target Batch Query Profile", "final_2026")
        sim_threshold = st.slider("Select Structural Match Threshold (%)", min_value=5, max_value=50, value=10, step=1) / 100.0
        
        if st.button("🔍 Run Order-Independent 4-Gram Plagiarism Sweep", type="primary"):
            with st.spinner("Streaming page footprints from Atlas cluster memory pools..."):
                cursor = transcripts_collection.find({"batch_id": target_batch, "status": "PROCESSED"})
                records = list(cursor)
                
                if not records:
                    st.error("No valid processed records located in database for this batch.")
                else:
                    flagged_pairs = check_classroom_plagiarism(records, similarity_threshold=sim_threshold)
                    st.metric(label="Total High-Risk Copied Pairs Flagged", value=len(flagged_pairs))
                    st.markdown("---")
                    
                    for idx, pair in enumerate(flagged_pairs, start=1):
                        with st.expander(f"⚠️ CASE #{idx}: {pair['student_a']} ⚡ {pair['student_b']} ── Overall Severity Match Score: {pair['overall_severity_score']}%"):
                            st.write(f"**Total structural questions with copy footprints:** `{pair['total_questions_flagged']}`")
                            
                            for f_idx, block in enumerate(pair["flagged_questions_breakdown"], start=1):
                                st.markdown(f"#### Match #{f_idx} ── `{block['question_context']}`")
                                c1, c2, c3 = st.columns(3)
                                with c1:
                                    st.caption(f"👤 **{pair['student_a']}** Location:")
                                    st.markdown(f"`{block['student_a_page']}`")
                                with c2:
                                    st.caption(f"👤 **{pair['student_b']}** Location:")
                                    st.markdown(f"`{block['student_b_page']}`")
                                with c3:
                                    st.caption("📊 Question Match:")
                                    st.markdown(f"**{block['match_percentage']}%**")
                                
                                st.markdown(f"**Text Neighborhood Preview:**")
                                st.code(block["context_anchor"], language="text")
                                
                                st.markdown("**Captured Phrase Fingerprints:**")
                                for phrase in block["evidence_phrases"]:
                                    st.markdown(f"- :red[`\"{phrase}\"`]")
                                st.markdown("---")
                                
                                
                                
# import streamlit as st
# import re
# from core.database import transcripts_collection, grades_collection

# st.title("⚖️ Human-in-the-Loop (HITL) Review Dashboard")
# st.markdown("---")

# # 1. FETCH ACTIVE DATA FROM MONGODB ATLAS
# # (In production, replace these strings with session-state values for the active student)
# active_student = "TOPPER_DEMO"
# target_batch = "final_2026"

# # A. Pull the single comprehensive question-wise grade card computed by LangGraph
# grade_record = grades_collection.find_one({"student_id": active_student, "batch_id": target_batch})

# # B. Pull all page-wise transcripts for this student to rebuild their continuous paper
# page_cursor = transcripts_collection.find({"student_id": active_student, "batch_id": target_batch, "status": "PROCESSED"}).sort("page_number", 1)
# page_docs = list(page_cursor)

# # ========================================================
# # 2. THE ALIGNMENT LAYER: Map Page-Wise Text to Question Keys
# # ========================================================
# @st.cache_data
# def rebuild_and_segment_student_paper(documents):
#     """Stitches page transcripts and separates them cleanly into answer blocks."""
#     # Stitch everything into one ordered master text string
#     full_student_text = " ".join([doc.get("extracted_text", "") for doc in documents])
    
#     # Use your exact verified regex pattern to find where answers start
#     q_marker_pattern = r'(?:ans|question|q)\s*\.?\s*\(?([0-9]+|[ivxlcdmIVXLCDM]+)\)?\b'
#     matches = list(re.finditer(q_marker_pattern, full_student_text, re.IGNORECASE))
    
#     text_by_question = {}
    
#     for i, match in enumerate(matches):
#         q_num = match.group(1).upper()  # e.g., "21" or "III"
#         start_pos = match.end()         # Start reading after the "Ans 21." marker text
#         end_pos = matches[i+1].start() if i + 1 < len(matches) else len(full_student_text)
        
#         # Save the pure answer text block inside our mapping dictionary
#         text_by_question[q_num] = full_student_text[start_pos:end_pos].strip()
        
#     return text_by_question

# # Execute the layout mapper execution check
# ui_text_lookup = rebuild_and_segment_student_paper(page_docs)

# # ========================================================
# # 3. RENDER THE ALIGNED USER INTERFACE
# # ========================================================
# if grade_record:
#     st.markdown(f"#### Reviewing Evaluation Record: `{active_student}` | Cumulative Score: **{grade_record.get('total_marks_awarded', 0)} / {grade_record.get('total_max_marks', 50)}**")
#     st.markdown("---")
    
#     # Loop directly over your structured question array inside your evaluation document
#     # grade_record["question_breakdown"] looks like: [{"q_num": "21", "max": 5, "awarded": 4.5, "justification": "..."}]
#     for idx, q_block in enumerate(grade_record.get("question_breakdown", [])):
        
#         # 🌟 DEFENSIVE KEY DETECTION: Auto-detects what name your LangGraph agent used
#         possible_keys = ["q_num", "question_number", "question", "q_no", "q"]
#         q_num_raw = None
        
#         for k in possible_keys:
#             if k in q_block:
#                 q_num_raw = q_block[k]
#                 break
                
#         # Fallback if no key matches so the dashboard still displays safely
#         if q_num_raw is None:
#             q_num_raw = f"Unknown-{idx}"
            
#         normalized_q_num = str(q_num_raw).upper().strip()
        
#         # Similarly handle variations in score/justification fields safely
#         max_marks = q_block.get("max", q_block.get("max_marks", 5.0))
#         awarded_marks = q_block.get("awarded", q_block.get("score", q_block.get("marks", 0.0)))
#         justification = q_block.get("justification", q_block.get("feedback", "No justification provided."))
        
#         # --- NOW RENDER THE UI CARD SECURELY ---
#         st.subheader(f"❓ Question {q_num_raw} (Weight: {max_marks} Marks)")
        
#         col_left, col_right = st.columns([1, 1])
        
#         with col_left:
#             st.info("📝 **Extracted Handwritten Script Content:**")
#             extracted_answer_text = ui_text_lookup.get(normalized_q_num, "⚠️ Error: Question marker header text could not be located on pages.")
#             st.code(extracted_answer_text, language="text")
            
#         with col_right:
#             st.warning("🤖 **AI-Proposed Scoring Justification Metrics:**")
#             st.write(justification)
            
#             new_score = st.number_input(
#                 f"Review / Override Score (Q{q_num_raw})", 
#                 min_value=0.0, 
#                 max_value=float(max_marks), 
#                 value=float(awarded_marks), 
#                 step=0.5,
#                 key=f"score_input_{normalized_q_num}"
#             )
            
#             c1, c2 = st.columns(2)
#             with c1:
#                 if st.button(f"✅ Approve Q{q_num_raw}", key=f"app_{normalized_q_num}", use_container_width=True):
#                     st.toast(f"Question {q_num_raw} grading contract verified and saved!")
#             with c2:
#                 if st.button(f"⚠️ Override Q{q_num_raw}", key=f"ovr_{normalized_q_num}", use_container_width=True):
#                     st.toast(f"Database overridden for Question {q_num_raw} with custom mark value: {new_score}")
#         st.markdown("---")                                