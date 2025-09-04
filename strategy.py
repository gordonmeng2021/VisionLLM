#!/usr/bin/env python3
"""
Strategy Analysis Tool
Analyzes candlestick chart images to detect candles and color signals for trading strategy.
"""

import numpy as np
from PIL import Image
import json
import sys
import os

class CandleStrategyAnalyzer:
    def __init__(self, image_path):
        """
        Initialize the strategy analyzer.
        
        Args:
            image_path (str): Path to the candlestick chart image
        """
        self.image_path = image_path
        self.image_array = None
        self.rgb_image = None
        self.candle_positions = []
        self.candle_width = None
        
        # Color detection rules (same as unified_color_detector.py)
        self.color_rules = {
            'red': [
                lambda r, g, b: r > max(g, b) * 1.2,   # Red dominant but not as strict
                lambda r, g, b: r > 100,               # High red value
                lambda r, g, b: g < r * 0.6,           # Green much lower than red (stricter to avoid orange)
                lambda r, g, b: b < r * 0.6,           # Blue much lower than red
                lambda r, g, b: r - g > 50,            # Red significantly higher than green (avoid orange)
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 40,  # Good color variation
            ],
            'green': [
                lambda r, g, b: g > max(r, b),         # Green is highest component
                lambda r, g, b: g > 50,                # Minimum green value
                lambda r, g, b: g - max(r, b) > 10,    # Green noticeably higher (more lenient)
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 15,  # Some color variation
                lambda r, g, b: g > 80 or (g > r * 1.5 and g > b * 0.8),  # Either bright green OR green dominant over red with reasonable blue
            ],
            'orange': [
                lambda r, g, b: r > g and g > b,       # R > G > B
                lambda r, g, b: r > 80,                # High red
                lambda r, g, b: g > 30 and g < r * 0.8,  # Medium green
                lambda r, g, b: b < min(r, g) * 0.5,   # Low blue
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 25,  # Color variation
            ],
            'purple': [
                lambda r, g, b: b >= max(r, g) * 0.7,  # Blue significant
                lambda r, g, b: g < r and g < b,       # Green lower than R and B
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 20,  # Color variation
                lambda r, g, b: r > 20,                # Red present
                lambda r, g, b: b > 30,                # Blue present
            ],
            'yellow': [
                lambda r, g, b: r > 100 and g > 100,   # High red and green
                lambda r, g, b: abs(int(r) - int(g)) < 80,       # Red and green similar
                lambda r, g, b: b < min(r, g) * 0.65,  # Blue less than 65% of min(R,G)
                lambda r, g, b: b < 150,               # Blue absolute limit
                lambda r, g, b: min(r, g) > max(r, g) * 0.6,   # R and G reasonably close
                lambda r, g, b: int(r) + int(g) > 2 * int(b) + 50,    # Yellow color space
                lambda r, g, b: r > g * 0.7 and g > r * 0.7,   # Neither R nor G dominates
                lambda r, g, b: r > 50 and g > 50,     # Minimum brightness
            ],
            'blue': [
                lambda r, g, b: b > max(r, g) * 1.2,   # Blue significantly dominant
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 15,  # Color variation
                lambda r, g, b: b > 40,                # Blue present
            ]
        }
    
    def load_image(self):
        """Load and prepare the image for analysis."""
        try:
            pil_image = Image.open(self.image_path)
            self.image_array = np.array(pil_image)
            print(f"✅ Image loaded: {self.image_array.shape}")
            
            # Convert to RGB (handle RGBA)
            if len(self.image_array.shape) == 3:
                if self.image_array.shape[2] == 4:  # RGBA
                    self.rgb_image = self.image_array[:, :, :3]
                else:  # RGB
                    self.rgb_image = self.image_array
            else:
                # print("❌ Unsupported image format")
                return False
            
            # print(f"✅ RGB image shape: {self.rgb_image.shape}")
            return True
            
        except Exception as e:
            # print(f"❌ Error loading image: {e}")
            return False
    
    def detect_candles(self):
        """Detect candles by finding horizontal continuity of red/green pixels."""
        print("🕯️  Detecting candles using horizontal continuity approach...")
        
        height, width = self.rgb_image.shape[:2]
        
        # Step 1: Create a horizontal color map - for each x position, check if ANY pixel in that column is red or green
        x_color_map = []  # List of (x, color) for each x position that has red or green pixels
        
        # print("🎨 Scanning horizontal positions for red/green pixels...")
        for x in range(width):
            has_red = False
            has_green = False
            
            # Check entire column for any red or green pixels
            for y in range(height):
                r, g, b = self.rgb_image[y, x]
                
                # Check for red pixels
                if not has_red and all(rule(r, g, b) for rule in self.color_rules['red']):
                    has_red = True
                
                # Check for green pixels  
                if not has_green and all(rule(r, g, b) for rule in self.color_rules['green']):
                    has_green = True
                
                # Early exit if both found
                if has_red and has_green:
                    break
            
            # Prioritize red over green if both present (red candles are more common)
            if has_red:
                x_color_map.append((x, 'red'))
            elif has_green:
                x_color_map.append((x, 'green'))
        
        # print(f"📍 Found {len(x_color_map)} x-positions with red/green pixels")
        
        if not x_color_map:
            # print("❌ No red/green pixels found")
            return []
        
        # Step 2: Find continuous horizontal segments of the same color
        segments = []
        current_segment = None
        
        for x, color in x_color_map:
            if current_segment is None:
                # Start new segment
                current_segment = {
                    'left': x,
                    'right': x,
                    'color': color,
                    'width': 1
                }
            elif current_segment['color'] == color and x == current_segment['right'] + 1:
                # Extend current segment (continuous)
                current_segment['right'] = x
                current_segment['width'] = current_segment['right'] - current_segment['left'] + 1
            else:
                # Finish current segment and start new one
                segments.append(current_segment)
                current_segment = {
                    'left': x,
                    'right': x,
                    'color': color,
                    'width': 1
                }
        
        # Don't forget the last segment
        if current_segment:
            segments.append(current_segment)
        
        # print(f"🔍 Found {len(segments)} continuous color segments:")
        # for i, seg in enumerate(segments):
            # print(f"  Segment {i+1}: {seg['color']} x={seg['left']}-{seg['right']} (width={seg['width']})")
        
        # Step 3: Analyze segment widths to identify candle pattern
        if not segments:
            # print("❌ No segments found")
            return []
        
        # Get all segment widths
        widths = [seg['width'] for seg in segments]
        width_counts = {}
        for w in widths:
            width_counts[w] = width_counts.get(w, 0) + 1
        
        # print(f"📊 Width distribution: {dict(sorted(width_counts.items()))}")
        
        # Find the most common width (likely the candle width)
        most_common_width = max(width_counts.items(), key=lambda x: x[1])[0]
        # print(f"📏 Most common width: {most_common_width} pixels (appears {width_counts[most_common_width]} times)")
        
        # Step 4: Filter segments to find candles based on the most common width
        candles = []
        tolerance = max(1, most_common_width // 4)  # Allow some tolerance
        
        for seg in segments:
            # Consider segments with width close to the most common width as candles
            if abs(seg['width'] - most_common_width) <= tolerance:
                center = (seg['left'] + seg['right']) // 2
                candles.append({
                    'left': seg['left'],
                    'right': seg['right'],
                    'center': center,
                    'width': seg['width'],
                    'color': seg['color']
                })
        
        # Step 5: If we don't have enough candles, try with more flexible criteria
        if len(candles) < 5:  # Expect at least 5 candles typically
            print("🔄 Not enough candles found, trying more flexible approach...")
            
            # Try with larger tolerance or different width
            sorted_widths = sorted(width_counts.items(), key=lambda x: x[1], reverse=True)
            
            for width, count in sorted_widths[:3]:  # Try top 3 most common widths
                candles = []
                tolerance = max(2, width // 3)  # More flexible tolerance
                
                for seg in segments:
                    if abs(seg['width'] - width) <= tolerance:
                        center = (seg['left'] + seg['right']) // 2
                        candles.append({
                            'left': seg['left'],
                            'right': seg['right'],
                            'center': center,
                            'width': seg['width'],
                            'color': seg['color']
                        })
                
                print(f"📊 Trying width {width} (±{tolerance}): found {len(candles)} candles")
                if len(candles) >= 8:  # Good number of candles
                    most_common_width = width
                    break
        
        self.candle_positions = candles
        self.candle_width = most_common_width
        
        # print(f"📊 Detected {len(candles)} candles")
        # print(f"📏 Candle width: {most_common_width} pixels")
        
        # print(f"🕯️  Final candle positions:")
        # for i, candle in enumerate(candles):
            # print(f"  Candle {i+1}: x={candle['center']} ({candle['color']}, left={candle['left']}, right={candle['right']}, width={candle['width']})")
        return candles
    
    def get_second_rightmost_candle(self):
        """Get the second rightmost candle's midpoint."""
        if len(self.candle_positions) < 2:
            # print("❌ Need at least 2 candles for analysis")
            return None
        
        # Sort candles by center position (rightmost first)
        sorted_candles = sorted(self.candle_positions, key=lambda c: c['center'], reverse=True)
        second_rightmost = sorted_candles[1]
        
        # print(f"🎯 Second rightmost candle center: x={second_rightmost['center']}")
        return second_rightmost
    
    def detect_color_at_position(self, color_name, x, y):
        """Detect if a specific color is present at given coordinates."""
        if (x < 0 or x >= self.rgb_image.shape[1] or 
            y < 0 or y >= self.rgb_image.shape[0]):
            return False
        
        r, g, b = self.rgb_image[y, x]
        
        if color_name not in self.color_rules:
            return False
        
        rules = self.color_rules[color_name]
        return all(rule(r, g, b) for rule in rules)
    
    def scan_vertical_line_for_colors(self, x, colors, direction='both'):
        """Scan a vertical line for specific colors and return detailed results."""
        height = self.rgb_image.shape[0]
        
        # Determine scan range based on direction
        if direction == 'down':
            y_range = range(height // 2, height)  # From middle down
        elif direction == 'up':
            y_range = range(0, height // 2)  # From top to middle
        else:  # 'both'
            y_range = range(height)  # Entire height
        
        # print(f"🔍 Scanning x={x} for {colors} in direction '{direction}' (y range: {min(y_range)}-{max(y_range)})")
        
        color_detections = {}
        for color in colors:
            color_detections[color] = []
        
        for y in y_range:
            for color in colors:
                if self.detect_color_at_position(color, x, y):
                    color_detections[color].append(y)
        
        # Report findings and return first color found
        for color in colors:
            if color_detections[color]:
                print(f"🎨 Found {len(color_detections[color])} {color} pixels at x={x}: y positions {color_detections[color][:5]}{'...' if len(color_detections[color]) > 5 else ''}")
                return color  # Return first color found
        
        # print(f"❌ No target colors found at x={x}")
        return 'none'
    
    def analyze_stm_signal(self, candle_x):
        """Analyze STM signal by looking down from candle midpoint for orange/purple."""
        # print(f"🔍 Analyzing STM signal at x={candle_x} (looking down)")
        
        color_found = self.scan_vertical_line_for_colors(candle_x, ['orange', 'purple'], 'down')
        
        if color_found == 'orange':
            return 'buy'
        elif color_found == 'purple':
            return 'sell'
        else:
            return 'none'
    
    def analyze_td_signal(self, candle_x):
        """Analyze TD signal by looking up and down from candle midpoint for yellow/blue."""
        # print(f"🔍 Analyzing TD signal at x={candle_x} (looking up and down)")
        
        color_found = self.scan_vertical_line_for_colors(candle_x, ['yellow', 'blue'], 'both')
        
        if color_found == 'yellow':
            return 'buy'
        elif color_found == 'blue':
            return 'sell'
        else:
            return 'none'
    
    def run_analysis(self):
        """Run the complete strategy analysis."""
        # print("🚀 Starting Strategy Analysis")
        # print("=" * 50)
        
        # Load image
        if not self.load_image():
            return {"error": "Failed to load image"}
        
        # Detect candles
        candles = self.detect_candles()
        if not candles:
            return {"error": "No candles detected"}
        
        # Get second rightmost candle
        second_rightmost = self.get_second_rightmost_candle()
        if not second_rightmost:
            return {"error": "Cannot find second rightmost candle"}
        
        candle_x = second_rightmost['center']
        
        # Analyze signals
        print("\n" + "=" * 50)
        print("📈 SIGNAL ANALYSIS")
        print("=" * 50)
        
        stm_signal = self.analyze_stm_signal(candle_x)
        td_signal = self.analyze_td_signal(candle_x)
        
        # Prepare results
        results = {
            "STM": stm_signal,
            "TD": td_signal
        }
        
        print(f"\n🎯 FINAL RESULTS:")
        print(f"STM Signal: {stm_signal}")
        print(f"TD Signal: {td_signal}")
        print(f"JSON Output: {json.dumps(results)}")
        
        return results

def main():
    """Main function to run the strategy analysis."""
    image_path = 'cropped_images/test.png'
    
    if not os.path.exists(image_path):
        # print(f"❌ Image not found: {image_path}")
        return
    
    # Create analyzer
    analyzer = CandleStrategyAnalyzer(image_path)
    
    # Run analysis
    results = analyzer.run_analysis()
    
    # Output final JSON
    if "error" not in results:
        print(f"\n🎉 Analysis Complete!")
        print(f"Final JSON: {json.dumps(results)}")
    else:
        # print(f"\n❌ Analysis Failed: {results['error']}")

if __name__ == "__main__":
    main()
