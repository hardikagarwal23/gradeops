import re

def clean_and_tokenize(text: str) -> list:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return text.split()

def generate_ngrams(words: list, n: int = 4) -> set:
    if len(words) < n:
        return set()
    return set(["_".join(words[i:i+n]) for i in range(len(words) - n + 1)])

def calculate_jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    return float(len(set_a.intersection(set_b))) / len(set_a.union(set_b))

def check_classroom_plagiarism(batch_documents: list, similarity_threshold: float = 0.20) -> list:
    flagged_pairs = []
    
    # Structure: { "student_id": { "question_number": {"text": "...", "pages":} } }
    student_answers_registry = {}
    all_detected_questions = set()

    # 🌟 PRODUCTION-GRADE REGEX: Strictly captures clean integers or valid Roman numerals.
    # It explicitly filters out regular trailing vocabulary words like "hip", "are", or "the".
    q_marker_pattern = r'(?:ans|question|q)\s*\.?\s*\(?([0-9]+|[ivxlcdmIVXLCDM]+)\)?\b'

    for doc in batch_documents:
        stu_id = doc["student_id"]
        page_num = doc.get("page_number", "Unknown")
        raw_text = doc.get("extracted_text", "")

        if stu_id not in student_answers_registry:
            student_answers_registry[stu_id] = {}

        matches = list(re.finditer(q_marker_pattern, raw_text, re.IGNORECASE))
        
        if not matches:
            # FIX: Universal tag for unmarked chunks so they can cross-compare across different pages
            q_key = f"UNMARKED"
            if q_key not in student_answers_registry[stu_id]:
                student_answers_registry[stu_id][q_key] = {"text": "", "pages": []}
            student_answers_registry[stu_id][q_key]["text"] += " " + raw_text
            student_answers_registry[stu_id][q_key]["pages"].append(page_num)
            all_detected_questions.add(q_key)
            continue

        # FIX: Capture any preamble text written before the first discovered question marker
        if matches[0].start() > 0:
            preamble_text = raw_text[:matches[0].start()].strip()
            if len(clean_and_tokenize(preamble_text)) > 5: # Only log if it contains substantial text
                p_key = "UNMARKED"
                if p_key not in student_answers_registry[stu_id]:
                    student_answers_registry[stu_id][p_key] = {"text": "", "pages": []}
                student_answers_registry[stu_id][p_key]["text"] += " " + preamble_text
                student_answers_registry[stu_id][p_key]["pages"].append(page_num)
                all_detected_questions.add(p_key)

        for i, match in enumerate(matches):
            q_num = match.group(1).upper() 
            start_pos = match.end() # FIX: Start after the match marker (e.g. "Ans 1.") to isolate pure answer text
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(raw_text)
            
            answer_content = raw_text[start_pos:end_pos].strip()
            
            if q_num not in student_answers_registry[stu_id]:
                student_answers_registry[stu_id][q_num] = {"text": "", "pages": []}
            
            student_answers_registry[stu_id][q_num]["text"] += " " + answer_content
            # FIX: Track all pages this question appears on instead of overwriting
            if page_num not in student_answers_registry[stu_id][q_num]["pages"]:
                student_answers_registry[stu_id][q_num]["pages"].append(page_num)
            all_detected_questions.add(q_num)

    detected_students = list(student_answers_registry.keys())
    num_students = len(detected_students)

    for i in range(num_students):
        for j in range(i + 1, num_students):
            stu_a = detected_students[i]
            stu_b = detected_students[j]
            
            question_matches = []
            
            for q_num in all_detected_questions:
                data_a = student_answers_registry[stu_a].get(q_num)
                data_b = student_answers_registry[stu_b].get(q_num)
                
                if not data_a or not data_b:
                    continue
                    
                words_a = clean_and_tokenize(data_a["text"])
                words_b = clean_and_tokenize(data_b["text"])
                
                if len(words_a) < 12 or len(words_b) < 12:
                    continue
                    
                ngrams_a = generate_ngrams(words_a, n=4)
                ngrams_b = generate_ngrams(words_b, n=4)
                
                score = calculate_jaccard_similarity(ngrams_a, ngrams_b)
                
                if score >= similarity_threshold:
                    intersection = list(ngrams_a.intersection(ngrams_b))
                    evidence = [p.replace("_", " ").capitalize() for p in intersection[:2]]
                    
                    # Formatting pages cleanly for human review strings
                    pages_a_str = ", ".join(map(str, data_a["pages"]))
                    pages_b_str = ", ".join(map(str, data_b["pages"]))
                    
                    question_matches.append({
                        "question_context": f"Question {q_num}" if q_num != "UNMARKED" else "Unmarked Context Block",
                        "match_percentage": round(score * 100, 2),
                        "student_a_page": f"Page(s) {pages_a_str}",
                        "student_b_page": f"Page(s) {pages_b_str}",
                        "context_anchor": " ".join(words_a[:10]) + "...",
                        "evidence_phrases": evidence
                    })
            
            if question_matches:
                avg_severity = sum(q["match_percentage"] for q in question_matches) / len(question_matches)
                flagged_pairs.append({
                    "student_a": stu_a,
                    "student_b": stu_b,
                    "overall_severity_score": round(avg_severity, 2),
                    "total_questions_flagged": len(question_matches),
                    "flagged_questions_breakdown": sorted(question_matches, key=lambda x: x["match_percentage"], reverse=True)
                })
                
    return sorted(flagged_pairs, key=lambda x: x["overall_severity_score"], reverse=True)
