import json
from core.database import transcripts_collection
from core.plagiarism_checker import (
    check_classroom_plagiarism, 
    clean_and_tokenize, 
    generate_ngrams, 
    calculate_jaccard_similarity
)

def run_local_terminal_test():
    target_batch = "final_2026"
    
    print("====================================================")
    print(f"🔍 LOCAL ANALYSIS: PLAGIARISM SWEEP FOR BATCH '{target_batch}'")
    print("====================================================")
    
    # 1. Fetch all processed transcripts out of your mixed Atlas collection
    print("🛰️  Querying documents from MongoDB Atlas page_transcripts...")
    cursor = transcripts_collection.find({
        "batch_id": target_batch, 
        "status": "PROCESSED"
    })
    records = list(cursor)
    
    print(f"📥 Found {len(records)} total processed page frames in memory.")
    if not records:
        print("❌ Error: No matching transcripts found.")
        return
        
    print("\n🧮 Running main function execution check...")
    try:
        # threshold=0.08 requires a minimum average similarity index score of 8% across blocks
        flagged_pairs = check_classroom_plagiarism(records, similarity_threshold=0.08)
        
        print("====================================================")
        print(f"🚨 DETECTION REPORT: {len(flagged_pairs)} HIGH-RISK PAIRS FLAGGED")
        print("====================================================")
        
        if not flagged_pairs:
            print("🟢 Clear! No suspicious structural copying anomalies detected across paragraph windows.")
        else:
            for index, pair in enumerate(flagged_pairs, start=1):
                print(f"\n[CASE #{index}] 📍 OVERALL SEVERITY SCORE: {pair['overall_severity_score']}%")
                print(f"👥 Involved Students: {pair['student_a']} ⚡ {pair['student_b']}")
                print(f"🗂️  Total Flagged Sections/Answers: {pair['total_questions_flagged']}")
                print("\n📋 CLASSIFIED BREAKDOWN OF DETECTED MATCHES:")
                
                # Iterate through the array of structural text overlapping segment targets
                for flag_idx, block_match in enumerate(pair["flagged_questions_breakdown"], start=1):
                    print(f"   🔹 Match Section #{flag_idx} ── [ {block_match['question_context']} ]")
                    print(f"       📊 Text Similarity Match: {block_match['match_percentage']}%")
                    print(f"       📍 Student A Location: {block_match['student_a_page']} | Student B Location: {block_match['student_b_page']}")
                    print(f"       🔍 Text Preview: \"{block_match['context_anchor']}\"")
                    print("       📝 Verbatim Overlapping Phrases:")
                    for phrase in block_match["evidence_phrases"]:
                        print(f"       • \"{phrase}\"")
                    print("   " + "-" * 60)
                
    except Exception as e:
        print(f"❌ Core processing runtime crashed: {str(e)}")

    print("\n====================================================")
    print("🏁 STANDALONE BACKGROUND SWEEP FINISHED")
    print("====================================================")

if __name__ == "__main__":
    run_local_terminal_test()
