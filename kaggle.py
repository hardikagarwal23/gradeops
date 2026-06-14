import os
import sys
import asyncio
import time

# 1. INSERT NGROK AUTHTOKEN HERE
NGROK_TOKEN = "ABC"

print("🚀 Step 1: Syncing stable, pre-compiled framework binaries...")
!pip install -q -U uvicorn fastapi python-multipart nest-asyncio pyngrok bitsandbytes accelerate "transformers>=4.45.2" pillow

print("📦 Step 2: Loading Quantized Qwen2-VL-7B into VRAM (Instant Native Allocation)...")
# FIX: Core imports moved to the absolute top of the cell block execution track
import torch
import io
import base64
import nest_asyncio
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image
from pyngrok import ngrok
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig

# Apply async loops safely now that nest_asyncio is locked into the namespace map
nest_asyncio.apply()

device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = "unsloth/Qwen2-VL-7B-Instruct-bnb-4bit"

# Setup high-performance 4-bit packing configurations
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)

model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto"
)
processor = AutoProcessor.from_pretrained(model_id)
print(f"✅ High-Accuracy 7B Engine successfully anchored to hardware platform: {device.upper()}")

app = FastAPI()

class ImagePayload(BaseModel):
    image_base64: str

@app.post("/predict")
async def process_exam_page(payload: ImagePayload):
    try:
        img_bytes = base64.b64decode(payload.image_base64)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        messages = [
    {
        "role": "system",
        "content": [
            {
                "type": "text", 
                "text": (
                    "You are a bulletproof, literal academic transcription engine. "
                    "Your job is to extract the text and formulas from the student's answer script page.\n\n"
                    "Strict Ingestion Constraints:\n"
                    "1. Transcribe ONLY what the student has written on this single page. Never extrapolate or create multiple pages.\n"
                    "2. Do NOT recalculate or correct the math. If the student writes '61 / 305 = 0.2A', transcribe '0.2A' exactly as it appears. Do not change it.\n"
                    "3. Convert chemical formulas and structural drawings into clean, explicit text representations. "
                    "CRITICAL FOR ORGANIC CHEMISTRY: Look carefully ABOVE and BELOW the main carbon atoms for functional attachments (like double-bonded oxygen atoms \\|=O or \\|\\|O). "
                    "If you see an oxygen drawn vertically above a carbon, explicitly include it in your text using parenthetical notation or explicit symbols (e.g., transcribing an Aldehyde drawing as '-C(=O)-H' or '-C(O)-H', and a Ketone as '-C(=O)-' or '-C(O)-'). Never drop atoms that are drawn vertically."
                    "4. DIAGRAM TRANSCRIPTION RULE: When you encounter a hand-drawn diagram or physics schematic, do not use generic placeholder text. Instead, write a clear, objective one-sentence summary of the layout enclosed in brackets, and explicitly transcribe all handwritten labels, variables, and axis values inside or directly adjacent to that diagram.\n"
                    "5. CRITICAL VISUAL RULE: Ignore all tiny margin notes, rough calculations, or scratchpad checkmarks written on the far right/left edges of the paper. Focus EXCLUSIVELY on transcribing the main centralized rows of text and equations written by the student in the notebook lines. Do not recalculate their math."
                )
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Transcribe all written answers, question indices, text blocks, and math expressions from this single page line-for-word."}
        ]
    }
]
                                
        
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=image, padding=True, return_tensors="pt").to(device)
        
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=1024, do_sample=False, temperature=0.0, repetition_penalty=1.05)
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            output_text = processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
            
        return {"markdown_text": output_text.strip()}
        
    except Exception as e:
        return {"error": str(e)}

print("📡 Step 3: Routing Ngrok Gateway Proxy...")
ngrok.set_auth_token(NGROK_TOKEN)
try:
    ngrok.disconnect(public_tunnel.public_url)
except:
    pass

public_tunnel = ngrok.connect(8080)
print("\n==================================================================")
print(f"👉 YOUR LIVE UNLIMITED KAGGLE ENGINE ENDPOINT IS: {public_tunnel.public_url}")
print("==================================================================")

config = uvicorn.Config(app=app, host="127.0.0.1", port=8080, log_level="info")
server = uvicorn.Server(config)
loop = asyncio.get_event_loop()
loop.create_task(server.serve())
print("🟢 Server online and coupled with background execution handlers!")
