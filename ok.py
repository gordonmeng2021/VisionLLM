import ollama
import time

system_prompt = """
You are a world wide experienced Trader, best at analyzing charts in TradingView.
Your job is to analyze ONLY the latest candle (the rightmost one) in the chart and return the result in JSON format.

# Important notes: 
# 1. The Navy blue background means post-market, Orange background means pre-market, please ignore this color.
# 2. Ignore the right panel, it is the stock list.

Instructions for extracting values:
1. "symbol":  
   - Found in the top left corner of the chart, the symbol is just next to the search icon (e.g., QQQ, NVDA, AAPL).

2. "Tom DeMark Sequential Heatmap":  
   - Visible description: "green or red labels with number on it."
   - Nearby -> Maximum 3 candles on the left of the rightmost candle.
   - If the rightmost candle has a green label background, classify as "Down".
   - If the rightmost candle nearby has a white label background and nearby you see green labels, then classify as "Down"
   - If the rightmost candle has a red label background, classify as "Up"
   - If the rightmost candle nearby has a white label background and nearby you see red labels, then classify as "Up"
   - If the rightmost candle and nearby has no any label, classify as "None"

3. "Zig-zag Indicator":  
   - Visible description: "text patterns (like "AB=CD", "Expanding Triangle", "AntiGartley", etc.) with red or green background."
   - Nearby -> Maximum 3 candles on the left of the rightmost candle.
   - Check for any text patterns 'Nearby'. (like "AB=CD", "Expanding Triangle", "AntiGartley", etc.)
   - If text appears in a red background, classify as "Down"
   - If text appears in a green background, classify as "Up"
   - If no such pattern text is present, classify as "None"

4. "STM Indicator":  
   - The STM Indicator is the indicator at the bottom for the whole chart with a white line that oscillates above and below a baseline.
   - The indicator chart has two horizontal dotted lines marking the upper and lower thresholds. 
   - Interpretation of the latest value (rightmost value):
        1. If the white line has **entered or opened a red-highlighted area (above the upper dotted line)** → classify as "Down".
        2. If the white line has **entered or opened a green-highlighted area (below the lower dotted line)** → classify as "Up".
        3. If the white line is **between the two dotted lines (middle area)** → classify as "None".
        4. If the position is unclear or does not meet any of the above → classify as "None".

** YOU MUST return ONLY valid JSON format: 
{ 
    "symbol":"${symbol}", 
    "Tom DeMark Sequential Heatmap": "Up" | "Down" | "None", 
    "Zig-zag Indicator": "Up" | "Down" | "None", 
    "STM Indicator": "Up" | "Down" | "None", 
}
"""

time_start = time.time()
res = ollama.chat(
   #  model='qwen2.5vl:7b',
    model='qwen2.5vl:72b',
   #  model='llama3.2-vision:90b',
    messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user',
         'content': 'According to your instruction prompt, answer for the attached image',
         'images': ['./stock.png']}
    ]
)
time_end = time.time()
print(res['message']['content'])
print(f"Time taken: {time_end - time_start:.2f} seconds")

# both large llm takes too long.