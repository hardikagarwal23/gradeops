import base64
import requests
import time

# 🌟 PASTE YOUR LIVE KAGGLE NGROK URL HERE OR MOVE TO AN ENVIRONMENT VARIABLE
KAGGLE_TUNNEL_URL = "https://calicoed-fruitily-clair.ngrok-free.dev"

def extract_handwriting_with_retry(file_path: str, max_retries: int = 3) -> str:
    """
    Encodes a local disk image into base64 format and pipes it directly 
    over the Ngrok tunnel into the hosted Qwen2-VL-7B Kaggle endpoint.
    """
    endpoint = f"{KAGGLE_TUNNEL_URL.rstrip('/')}/predict"
    
    try:
        with open(file_path, "rb") as image_file:
            base64_encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        raise IOError(f"Failed to read asset image file from disk: {str(e)}")

    payload = {"image_base64": base64_encoded_string}
    
    for attempt in range(max_retries):
        try:
            response = requests.post(endpoint, json=payload, timeout=90)
            if response.status_code == 200:
                result_json = response.json()
                if "markdown_text" in result_json:
                    return result_json["markdown_text"]
                elif "error" in result_json:
                    raise Exception(f"Kaggle Core Error: {result_json['error']}")
            
            # If server is warming up or hit an accidental connection glitch
            print(f"⚠️ Tunnel status code {response.status_code} on attempt {attempt+1}. Retrying...")
            time.sleep(2)
        except requests.exceptions.RequestException as req_err:
            print(f"📡 Network connection retry warning (Attempt {attempt+1}): {str(req_err)}")
            time.sleep(3)

    raise Exception(f"❌ Critical Connection Fault: Failed to reach Kaggle endpoint at {endpoint}")
