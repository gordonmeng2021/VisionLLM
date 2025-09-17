#!/usr/bin/env python3
"""
Strategy Analysis Tool
Analyzes candlestick chart images to detect candles and color signals for trading strategy.
"""

import numpy as np
import json
import sys
import os
from color_detection_tools.unified_color_detector import UnifiedColorDetector

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
        
        # Use UnifiedColorDetector as the single source of truth for color rules
        self.unified_detector = UnifiedColorDetector(image_path)
        # Map to the plain list-of-rules format used by this analyzer
        self.color_rules = {
            color_name: color_info['rules']
            for color_name, color_info in self.unified_detector.color_rules.items()
        }
    
    def load_image(self):
        """Load and prepare the image for analysis."""
        # Delegate image loading to UnifiedColorDetector to keep consistency
        if not self.unified_detector.load_image():
            return False
        self.image_array = self.unified_detector.image_array
        self.rgb_image = self.unified_detector.rgb_image
        return True
    
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
    
    def validate_horizontal_line(self, color_name, x, y, pixels_range=30):
        """
        Validate if a color forms a horizontal line by checking exactly ±pixels_range around the detected pixel.
        
        Args:
            color_name (str): The color to validate
            x (int): X coordinate of the detected pixel
            y (int): Y coordinate of the detected pixel
            pixels_range (int): Range to check left and right (default 45)
        
        Returns:
            bool: True if horizontal line of exactly 90 pixels (45 left + 45 right) is found
        """
        if (x < 0 or x >= self.rgb_image.shape[1] or 
            y < 0 or y >= self.rgb_image.shape[0]):
            return False
        
        width = self.rgb_image.shape[1]
        
        # Check left side (exactly 45 pixels)
        left_valid = True
        for dx in range(1, pixels_range + 1):
            check_x = x - dx
            if check_x < 0:
                left_valid = False
                break
            if not self.detect_color_at_position(color_name, check_x, y):
                left_valid = False
                break
        
        # Check right side (exactly 45 pixels)
        right_valid = True
        for dx in range(1, pixels_range + 1):
            check_x = x + dx
            if check_x >= width:
                right_valid = False
                break
            if not self.detect_color_at_position(color_name, check_x, y):
                right_valid = False
                break
        
        # Valid horizontal line only if we have exactly 45 pixels on both sides
        return left_valid and right_valid
    
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
                # print(f"🎨 Found {len(color_detections[color])} {color} pixels at x={x}: y positions {color_detections[color][:5]}{'...' if len(color_detections[color]) > 5 else ''}")
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
    
    def scan_vertical_line_with_horizontal_validation(self, x, colors, direction='both'):
        """
        Scan a vertical line for specific colors and validate horizontal lines.
        
        Args:
            x (int): X coordinate to scan
            colors (list): List of colors to look for
            direction (str): 'up', 'down', or 'both'
        
        Returns:
            tuple: (color_found, validated_positions) where color_found is the first valid color
        """
        height = self.rgb_image.shape[0]
        
        # Determine scan range based on direction
        if direction == 'down':
            y_range = range(height // 2, height)  # From middle down
        elif direction == 'up':
            y_range = range(0, height // 2)  # From top to middle
        else:  # 'both'
            y_range = range(height)  # Entire height
        
        # print(f"🔍 Scanning x={x} for {colors} with horizontal validation in direction '{direction}'")
        
        for color in colors:
            validated_positions = []
            
            # Scan for the color
            for y in y_range:
                if self.detect_color_at_position(color, x, y):
                    # Found the color, now validate horizontal line
                    if self.validate_horizontal_line(color, x, y):
                        validated_positions.append(y)
            
            # If we found valid horizontal lines for this color, return it
            if validated_positions:
                # print(f"🎨 Found {len(validated_positions)} validated {color} horizontal lines at x={x}")
                # print(f"    Y positions: {validated_positions[:5]}{'...' if len(validated_positions) > 5 else ''}")
                return color, validated_positions
        
        # print(f"❌ No validated horizontal lines found at x={x}")
        return 'none', []
    
    def analyze_horizontal_line_signal(self, candle_x):
        """
        Analyze the new horizontal line indicator with correct logic:
        1. First check if vertical line hits aqua or fuchsia
        2. Only if hit, then validate horizontal line (90 pixels: 45 left + 45 right)
        
        Args:
            candle_x (int): X coordinate of the second rightmost candle
        
        Returns:
            str: 'buy' for fuchsia, 'sell' for aqua, 'none' if no valid horizontal lines found
        """
        # print(f"🔍 Analyzing Horizontal Line signal at x={candle_x} (looking up and down for aqua/fuchsia)")
        
        height = self.rgb_image.shape[0]
        
        # Step 1: First scan the vertical line to see if we hit aqua or fuchsia at all
        aqua_pixels = []
        fuchsia_pixels = []
        
        # print("🔍 Step 1: Scanning vertical line for aqua/fuchsia pixels...")
        for y in range(height):
            if self.detect_color_at_position('aqua', candle_x, y):
                aqua_pixels.append(y)
            elif self.detect_color_at_position('fuchsia', candle_x, y):
                fuchsia_pixels.append(y)
        
        # print(f"   Found {len(aqua_pixels)} aqua pixels and {len(fuchsia_pixels)} fuchsia pixels")
        
        # Step 2: If no aqua or fuchsia pixels found, return none
        if not aqua_pixels and not fuchsia_pixels:
            # print("❌ No aqua or fuchsia pixels found on vertical line")
            return 'none'
        
        # Step 3: Check horizontal line validation for found pixels
        # print("🔍 Step 2: Validating horizontal lines for detected pixels...")
        
        # Check fuchsia pixels first (priority for buy signal)
        if fuchsia_pixels:
            print(f"   Checking {len(fuchsia_pixels)} fuchsia pixels for horizontal validation...")
            for y in fuchsia_pixels:
                if self.validate_horizontal_line('fuchsia', candle_x, y):
                    print(f"✅ Valid fuchsia horizontal line found at y={y}")
                    return 'buy'
        
        # Check aqua pixels
        if aqua_pixels:
            print(f"   Checking {len(aqua_pixels)} aqua pixels for horizontal validation...")
            for y in aqua_pixels:
                if self.validate_horizontal_line('aqua', candle_x, y):
                    print(f"✅ Valid aqua horizontal line found at y={y}")
                    return 'sell'
        
        # print("❌ No valid horizontal lines found (90 pixel requirement not met)")
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
        # print("\n" + "=" * 50)
        # print("📈 SIGNAL ANALYSIS")
        # print("=" * 50)
        
        stm_signal = self.analyze_stm_signal(candle_x)
        td_signal = self.analyze_td_signal(candle_x)
        horizontal_line_signal = self.analyze_horizontal_line_signal(candle_x)
        
        # Prepare results
        results = {
            "STM": stm_signal,
            "TD": td_signal,
            "Zigzag": horizontal_line_signal
        }
        
        # print(f"\n🎯 FINAL RESULTS:")
        # print(f"STM Signal: {stm_signal}")
        # print(f"TD Signal: {td_signal}")
        # print(f"Horizontal Line Signal: {horizontal_line_signal}")
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
        pass

if __name__ == "__main__":
    main()
