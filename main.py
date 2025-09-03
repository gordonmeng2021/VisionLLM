import requests
import base64
import json
import os
import time
from datetime import datetime

def encode_image(image_path):
    """Convert image to base64"""
    start_time = time.time()
    try:
        with open(image_path, "rb") as image_file:
            result = base64.b64encode(image_file.read()).decode('utf-8')
        end_time = time.time()
        print(f"⏱️  Image encoding: {(end_time - start_time):.4f} seconds")
        return result
    except Exception as e:
        end_time = time.time()
        print(f"⏱️  Image encoding (failed): {(end_time - start_time):.4f} seconds")
        print(f"Error reading image: {e}")
        return None

def ask_about_image(image_path, question, system_prompt):
    """Send image and question to Qwen2.5-VL model with system prompt"""
    total_start = time.time()
    
    # Encode the image
    print("\n🔄 Starting image analysis...")
    encode_start = time.time()
    image_base64 = encode_image(image_path)
    encode_end = time.time()
    if not image_base64:
        return "Failed to read image"
    
    # Combine system prompt with user question
    prompt_start = time.time()
    full_prompt = f"{system_prompt}\n\nUser request: {question}"
    prompt_end = time.time()
    print(f"⏱️  Prompt preparation: {(prompt_end - prompt_start):.4f} seconds")
    
    # Prepare request
    payload_start = time.time()
    payload = {
        # "model": "qwen2.5vl:3b",  # Seems better than 7b
        # "model": "qwen2.5vl:7b",
        # "model": "llama3.2-vision:11b",
        # "model": "minicpm-v:8b", 
        "model": "llava:7b",
        "prompt": full_prompt,
        # "images": [image_base64],
        "stream": False
    }
    payload_end = time.time()
    print(f"⏱️  Payload preparation: {(payload_end - payload_start):.4f} seconds")
    
    try:
        print("🚀 Sending request to Ollama...")
        request_start = time.time()
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=60)
        request_end = time.time()
        print(f"⏱️  HTTP request: {(request_end - request_start):.4f} seconds")
        
        response.raise_for_status()
        
        parse_start = time.time()
        result = response.json()
        parse_end = time.time()
        print(f"⏱️  Response parsing: {(parse_end - parse_start):.4f} seconds")
        
        total_end = time.time()
        print(f"⏱️  Total analysis time: {(total_end - total_start):.4f} seconds")
        
        return result.get('response', 'No response received')
        
    except Exception as e:
        total_end = time.time()
        print(f"⏱️  Total analysis time (failed): {(total_end - total_start):.4f} seconds")
        return f"Error: {e}"

def main():
    print("Simple Vision Chat with Qwen2.5-VL")
    print("=" * 40)
    
    # System prompt (instruction for the AI)
    system_prompt = """
You are a world wide experienced Trader.
Your job is to analyze ONLY the latest candle (the rightmost one) in the chart and return the result in JSON format.

# Important notes: The Navy blue background means post-market, Orange background means pre-market, please ignore this color.

Instructions for extracting values:
1. "symbol":  
   - Found in the top left corner of the chart (e.g., QQQ, NVDA, AAPL).

2. "Tom DeMark Sequential Heatmap":  
   - Visible description: "green or red labels with number on it."
   - Nearby -> Maximum 3 candles on the left of the rightmost candle.
   - If the rightmost candle has a green label background, remember "Up" for the this indicator.  
   - If the rightmost candle has a red label background, remember "Down" for the this indicator.  
   - If the rightmost candle nearby has a white label background and nearby you see red labels, then remember "Down" for the this indicator.
   - If the rightmost candle nearby has a white label background and nearby you see green labels, then remember "Up" for the this indicator.
   - If the rightmost candle and nearby has no any label, remember "None" for the this indicator.

3. "Zig-zag Indicator":  
   - Visible description: "text patterns (like "AB=CD", "Expanding Triangle", "AntiGartley", etc.) with red or green background."
   - Check for any text patterns (like "AB=CD", "Expanding Triangle", "AntiGartley", etc.) near the latest candle (can be within the last 2 candles).  
   - If text appears in a red background, remember "Down" for the this indicator.  
   - If text appears in a green background, remember "Up" for the this indicator.  
   - If no such pattern text is present, remember "None" for the this indicator.

4. "STM Indicator":  
   - This is the bottom oscillator indicator.  
   - If the latest value is in a red-highlighted area, remember "Down" for the this indicator.  
   - If the latest value is in a green-highlighted area, remember "Up" for the this indicator.  
   - If the latest value is in the Middle area (i.e. In between 2 horizontal dotted lines), remember "None" for the this indicator.
   - If neither is clearly shown, remember "None" for the this indicator.

** YOU MUST return ONLY valid JSON format: 
{ 
    "symbol":"${symbol}", 
    "Tom DeMark Sequential Heatmap": "Up" | "Down" | "None", 
    "Zig-zag Indicator": "Up" | "Down" | "None", 
    "STM Indicator": "Up" | "Down" | "None", 
}
"""
    
    # Hardcoded image path - CHANGE THIS TO YOUR IMAGE
    image_path = "./stock.jpeg"  # Change this to your image path
    
    # Hardcoded question
    question = "According to your instruction prompt, return the answer for the following image: /Users/meng/Desktop/2025 Backtester/VisionLLM/stock.jpeg"
    
    print(f"Image: {image_path}")
    print(f"Question: {question}")
    print(f"System prompt: {system_prompt}")
    print("-" * 60)
    
    # Check if file exists
    file_check_start = time.time()
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        print("Please update the image_path variable in the code")
        return
    file_check_end = time.time()
    print(f"⏱️  File existence check: {(file_check_end - file_check_start):.4f} seconds")
    
    # Get response
    print(f"\n🕐 Starting analysis at: {datetime.now().strftime('%H:%M:%S')}")
    main_start = time.time()
    response = ask_about_image(image_path, question, system_prompt)
    main_end = time.time()
    print(f"⏱️  Main execution time: {(main_end - main_start):.4f} seconds")

    # Display result
    print("\n" + "=" * 60)
    print("RESPONSE:")
    print("=" * 60)
    print(response)
    print("=" * 60)
    
    # Summary of all timings
    print(f"\n📊 Performance Summary:")
    print(f"   • File check: {(file_check_end - file_check_start):.4f}s")
    print(f"   • Main execution: {(main_end - main_start):.4f}s")
    print(f"   • Total program time: {(main_end - file_check_start):.4f}s")

if __name__ == "__main__":
    main()