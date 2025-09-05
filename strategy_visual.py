#!/usr/bin/env python3
"""
Visual Strategy Analysis Tool
Analyzes candlestick chart images and creates visual output showing:
- Detected candle positions
- Second rightmost candle midpoint
- Vertical scan lines for color detection
- Color detection results with markers
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import sys
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime

class VisualCandleStrategyAnalyzer:
    def __init__(self, image_path):
        """
        Initialize the visual strategy analyzer.
        
        Args:
            image_path (str): Path to the candlestick chart image
        """
        self.image_path = image_path
        self.image_array = None
        self.rgb_image = None
        self.candle_positions = []
        self.candle_width = None
        
        # Color detection rules (same as strategy.py)
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
            ],
            'aqua': [
                lambda r, g, b: b > 100 and g > 100,   # High blue and green components
                lambda r, g, b: r < min(b, g) * 0.6,   # Red significantly lower than blue and green
                lambda r, g, b: abs(int(b) - int(g)) < 100,  # Blue and green should be reasonably similar
                lambda r, g, b: min(b, g) > max(b, g) * 0.7,  # Both blue and green should be substantial
                lambda r, g, b: g > 80,                # Ensure sufficient green to distinguish from pure blue
                lambda r, g, b: b > g * 0.8,           # Blue should be at least 80% of green value
                lambda r, g, b: int(b) + int(g) > 2 * int(r) + 80,   # Aqua color space rule
                lambda r, g, b: max(b, g, r) - min(b, g, r) > 30,  # Good color variation
            ],
            'fuchsia': [
                lambda r, g, b: r > 150 and b > 150,   # High red and blue
                lambda r, g, b: g < min(r, b) * 0.7,   # Green much lower than red and blue
                lambda r, g, b: abs(int(r) - int(b)) < 80,  # Red and blue should be reasonably similar
                lambda r, g, b: max(r, b) > g * 1.5,   # Either red or blue dominates over green
                lambda r, g, b: max(r, g, b) - min(r, g, b) > 40,  # Good color variation
                lambda r, g, b: int(r) + int(b) > 2 * int(g) + 100,   # Fuchsia color space rule
            ]
        }
    
    def load_image(self):
        """Load and prepare the image for analysis."""
        try:
            pil_image = Image.open(self.image_path)
            self.image_array = np.array(pil_image)
            # print(f"✅ Image loaded: {self.image_array.shape}")
            
            # Convert to RGB (handle RGBA)
            if len(self.image_array.shape) == 3:
                if self.image_array.shape[2] == 4:  # RGBA
                    self.rgb_image = self.image_array[:, :, :3]
                else:  # RGB
                    self.rgb_image = self.image_array
            else:
                print("❌ Unsupported image format")
                return False
            
            print(f"✅ RGB image shape: {self.rgb_image.shape}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading image: {e}")
            return False
    
    def detect_candles(self):
        """Detect candles by finding horizontal continuity of red/green pixels."""
        # print("🕯️  Detecting candles using horizontal continuity approach...")
        
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
            print("❌ No red/green pixels found")
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
            print("❌ No segments found")
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
            # print("🔄 Not enough candles found, trying more flexible approach...")
            
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
            print("❌ Need at least 2 candles for analysis")
            return None
        
        # Sort candles by center position (rightmost first)
        sorted_candles = sorted(self.candle_positions, key=lambda c: c['center'], reverse=True)
        second_rightmost = sorted_candles[1]
        
        print(f"🎯 Second rightmost candle center: x={second_rightmost['center']}")
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
    
    def validate_horizontal_line(self, color_name, x, y, pixels_range=45):
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
        
        print(f"🔍 Scanning x={x} for {colors} in direction '{direction}' (y range: {min(y_range)}-{max(y_range)})")
        
        color_detections = {}
        for color in colors:
            color_detections[color] = []
        
        for y in y_range:
            for color in colors:
                if self.detect_color_at_position(color, x, y):
                    color_detections[color].append(y)
        
        # Report findings and return first color found with positions
        for color in colors:
            if color_detections[color]:
                # print(f"🎨 Found {len(color_detections[color])} {color} pixels at x={x}: y positions {color_detections[color][:5]}{'...' if len(color_detections[color]) > 5 else ''}")
                return color, color_detections[color]  # Return color and positions
        
        # print(f"❌ No target colors found at x={x}")
        return 'none', []
    
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
        
        print(f"🔍 Scanning x={x} for {colors} with horizontal validation in direction '{direction}'")
        
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
                print(f"🎨 Found {len(validated_positions)} validated {color} horizontal lines at x={x}")
                print(f"    Y positions: {validated_positions[:5]}{'...' if len(validated_positions) > 5 else ''}")
                return color, validated_positions
        
        print(f"❌ No validated horizontal lines found at x={x}")
        return 'none', []
    
    def analyze_horizontal_line_signal(self, candle_x):
        """
        Analyze the new horizontal line indicator with correct logic:
        1. First check if vertical line hits aqua or fuchsia
        2. Only if hit, then validate horizontal line (90 pixels: 45 left + 45 right)
        
        Args:
            candle_x (int): X coordinate of the second rightmost candle
        
        Returns:
            tuple: (signal, aqua_pixels, fuchsia_pixels) for visualization
        """
        print(f"🔍 Analyzing Horizontal Line signal at x={candle_x} (looking up and down for aqua/fuchsia)")
        
        height = self.rgb_image.shape[0]
        
        # Step 1: First scan the vertical line to see if we hit aqua or fuchsia at all
        aqua_pixels = []
        fuchsia_pixels = []
        
        print("🔍 Step 1: Scanning vertical line for aqua/fuchsia pixels...")
        for y in range(height):
            if self.detect_color_at_position('aqua', candle_x, y):
                aqua_pixels.append(y)
            elif self.detect_color_at_position('fuchsia', candle_x, y):
                fuchsia_pixels.append(y)
        
        print(f"   Found {len(aqua_pixels)} aqua pixels and {len(fuchsia_pixels)} fuchsia pixels")
        
        # Step 2: If no aqua or fuchsia pixels found, return none
        if not aqua_pixels and not fuchsia_pixels:
            print("❌ No aqua or fuchsia pixels found on vertical line")
            return 'none', [], []
        
        # Step 3: Check horizontal line validation for found pixels
        print("🔍 Step 2: Validating horizontal lines for detected pixels...")
        
        # Check fuchsia pixels first (priority for buy signal)
        if fuchsia_pixels:
            print(f"   Checking {len(fuchsia_pixels)} fuchsia pixels for horizontal validation...")
            for y in fuchsia_pixels:
                if self.validate_horizontal_line('fuchsia', candle_x, y):
                    print(f"✅ Valid fuchsia horizontal line found at y={y}")
                    return 'buy', aqua_pixels, fuchsia_pixels
        
        # Check aqua pixels
        if aqua_pixels:
            print(f"   Checking {len(aqua_pixels)} aqua pixels for horizontal validation...")
            for y in aqua_pixels:
                if self.validate_horizontal_line('aqua', candle_x, y):
                    print(f"✅ Valid aqua horizontal line found at y={y}")
                    return 'sell', aqua_pixels, fuchsia_pixels
        
        print("❌ No valid horizontal lines found (90 pixel requirement not met)")
        return 'none', aqua_pixels, fuchsia_pixels
    
    def create_visual_analysis(self, candle_x):
        """Create a comprehensive visual analysis showing all detection steps."""
        print("🎨 Creating visual analysis...")
        
        # Create figure with multiple subplots (2x3 grid for the new indicator)
        fig, axes = plt.subplots(2, 3, figsize=(30, 16))
        fig.suptitle('Visual Strategy Analysis', fontsize=16, fontweight='bold')
        
        # 1. Original image with candle detection
        ax1 = axes[0, 0]
        ax1.imshow(self.rgb_image)
        ax1.set_title('1. Detected Candles', fontsize=14, fontweight='bold')
        
        # Mark all candles with their actual colors
        for i, candle in enumerate(self.candle_positions):
            # Choose color based on candle type
            edge_color = 'red' if candle.get('color') == 'red' else 'green' if candle.get('color') == 'green' else 'cyan'
            
            # Draw candle boundaries
            rect = patches.Rectangle((candle['left'], 0), candle['width'], self.rgb_image.shape[0], 
                                   linewidth=3, edgecolor=edge_color, facecolor='none', alpha=0.8)
            ax1.add_patch(rect)
            
            # Mark center
            ax1.axvline(x=candle['center'], color=edge_color, linestyle='--', alpha=0.8)
            ax1.text(candle['center'], 50, f'C{i+1}\n{candle.get("color", "?").upper()}', ha='center', va='center', 
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=edge_color, alpha=0.8, edgecolor='white'))
        
        # Highlight second rightmost candle
        second_rightmost = self.get_second_rightmost_candle()
        if second_rightmost:
            ax1.axvline(x=second_rightmost['center'], color='red', linewidth=3, alpha=0.9)
            ax1.text(second_rightmost['center'], 100, '2nd Rightmost\nCandle', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='red', alpha=0.8, edgecolor='white'))
        
        ax1.set_xlim(0, self.rgb_image.shape[1])
        ax1.set_ylim(self.rgb_image.shape[0], 0)  # Flip Y axis
        
        # 2. STM Analysis (looking down for orange/purple)
        ax2 = axes[0, 1]
        ax2.imshow(self.rgb_image)
        ax2.set_title('2. STM Analysis (Orange/Purple - Looking Down)', fontsize=14, fontweight='bold')
        
        # Mark scan line
        ax2.axvline(x=candle_x, color='yellow', linewidth=3, alpha=0.9)
        
        # Mark middle line (start of "down" scan)
        middle_y = self.rgb_image.shape[0] // 2
        ax2.axhline(y=middle_y, color='orange', linestyle='--', alpha=0.7)
        ax2.text(10, middle_y, 'Scan Start (Down)', va='center', 
                bbox=dict(boxstyle='round,pad=0.3', facecolor='orange', alpha=0.8))
        
        # Perform STM scan and mark detections
        stm_color, stm_positions = self.scan_vertical_line_for_colors(candle_x, ['orange', 'purple'], 'down')
        
        if stm_color != 'none':
            for y_pos in stm_positions[:10]:  # Show first 10 detections
                color_rgb = 'orange' if stm_color == 'orange' else 'purple'
                ax2.plot(candle_x, y_pos, 'o', color=color_rgb, markersize=8, alpha=0.8)
            
            # Add result text
            result_text = 'BUY' if stm_color == 'orange' else 'SELL'
            ax2.text(candle_x + 10, middle_y + 100, f'STM: {result_text}\n({stm_color} detected)', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor=color_rgb, alpha=0.8))
        else:
            ax2.text(candle_x + 10, middle_y + 100, 'STM: NONE\n(no colors)', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='gray', alpha=0.8))
        
        ax2.set_xlim(0, self.rgb_image.shape[1])
        ax2.set_ylim(self.rgb_image.shape[0], 0)
        
        # 3. TD Analysis (looking up and down for yellow/blue)
        ax3 = axes[1, 0]
        ax3.imshow(self.rgb_image)
        ax3.set_title('3. TD Analysis (Yellow/Blue - Looking Both Ways)', fontsize=14, fontweight='bold')
        
        # Mark scan line
        ax3.axvline(x=candle_x, color='magenta', linewidth=3, alpha=0.9)
        
        # Perform TD scan and mark detections
        td_color, td_positions = self.scan_vertical_line_for_colors(candle_x, ['yellow', 'blue'], 'both')
        
        if td_color != 'none':
            for y_pos in td_positions[:10]:  # Show first 10 detections
                color_rgb = 'yellow' if td_color == 'yellow' else 'blue'
                ax3.plot(candle_x, y_pos, 's', color=color_rgb, markersize=8, alpha=0.8)
            
            # Add result text
            result_text = 'BUY' if td_color == 'yellow' else 'SELL'
            ax3.text(candle_x + 10, 200, f'TD: {result_text}\n({td_color} detected)', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor=color_rgb, alpha=0.8))
        else:
            ax3.text(candle_x + 10, 200, 'TD: NONE\n(no colors)', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='gray', alpha=0.8))
        
        ax3.set_xlim(0, self.rgb_image.shape[1])
        ax3.set_ylim(self.rgb_image.shape[0], 0)
        
        # 4. Horizontal Line Analysis (looking up and down for aqua/fuchsia)
        ax4 = axes[1, 0]
        ax4.imshow(self.rgb_image)
        ax4.set_title('4. Horizontal Line Analysis (Aqua/Fuchsia - Both Ways)', fontsize=14, fontweight='bold')
        
        # Mark scan line
        ax4.axvline(x=candle_x, color='cyan', linewidth=3, alpha=0.9)
        
        # Perform Horizontal Line analysis with correct logic
        hl_signal, aqua_pixels, fuchsia_pixels = self.analyze_horizontal_line_signal(candle_x)
        
        # Mark all detected pixels (before validation)
        for y_pos in aqua_pixels[:10]:  # Show first 10 aqua pixels
            ax4.plot(candle_x, y_pos, 'o', color='aqua', markersize=6, alpha=0.6)
        
        for y_pos in fuchsia_pixels[:10]:  # Show first 10 fuchsia pixels
            ax4.plot(candle_x, y_pos, 'o', color='fuchsia', markersize=6, alpha=0.6)
        
        # Show validation results
        if hl_signal != 'none':
            # Find which pixels passed validation
            validated_color = 'aqua' if hl_signal == 'sell' else 'fuchsia'
            pixels_to_check = aqua_pixels if hl_signal == 'sell' else fuchsia_pixels
            
            for y_pos in pixels_to_check:
                if self.validate_horizontal_line(validated_color, candle_x, y_pos):
                    # Mark validated horizontal line
                    ax4.plot(candle_x, y_pos, 'D', color=validated_color, markersize=12, alpha=1.0)
                    ax4.axhline(y=y_pos, color=validated_color, linestyle='-', alpha=0.5, linewidth=3)
                    break  # Only show the first valid one
            
            # Add result text
            result_text = 'SELL' if hl_signal == 'sell' else 'BUY'
            ax4.text(candle_x + 10, 150, f'HL: {result_text}\n({validated_color} 90px line)', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor=validated_color, alpha=0.8))
        else:
            reason = 'no pixels found' if not aqua_pixels and not fuchsia_pixels else 'no 90px lines'
            ax4.text(candle_x + 10, 150, f'HL: NONE\n({reason})', 
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='gray', alpha=0.8))
        
        ax4.set_xlim(0, self.rgb_image.shape[1])
        ax4.set_ylim(self.rgb_image.shape[0], 0)
        
        # 5. Empty placeholder or additional analysis
        ax5 = axes[0, 2]
        ax5.axis('off')
        ax5.set_title('5. Horizontal Line Validation Detail', fontsize=14, fontweight='bold')
        
        # Show horizontal line validation visualization
        if hl_signal != 'none' and (aqua_pixels or fuchsia_pixels):
            # Find the first validated line
            validated_color = 'aqua' if hl_signal == 'sell' else 'fuchsia'
            pixels_to_check = aqua_pixels if hl_signal == 'sell' else fuchsia_pixels
            
            first_valid_pos = None
            for y_pos in pixels_to_check:
                if self.validate_horizontal_line(validated_color, candle_x, y_pos):
                    first_valid_pos = y_pos
                    break
            
            if first_valid_pos is not None:
                # Create a zoomed view of the validated horizontal line
                y_start = max(0, first_valid_pos - 20)
                y_end = min(self.rgb_image.shape[0], first_valid_pos + 20)
                x_start = max(0, candle_x - 60)
                x_end = min(self.rgb_image.shape[1], candle_x + 60)
                
                cropped_region = self.rgb_image[y_start:y_end, x_start:x_end]
                ax5.imshow(cropped_region)
                ax5.axhline(y=first_valid_pos-y_start, color=validated_color, linewidth=3, alpha=0.8)
                ax5.axvline(x=candle_x-x_start, color='white', linewidth=2, alpha=0.8)
                ax5.set_title(f'Validated Line Detail\n{validated_color.upper()} at Y={first_valid_pos}')
            else:
                ax5.text(0.5, 0.5, 'Pixels found but\nno valid 90px lines', ha='center', va='center', 
                        transform=ax5.transAxes, fontsize=14,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='orange', alpha=0.8))
        else:
            ax5.text(0.5, 0.5, 'No aqua/fuchsia\npixels detected', ha='center', va='center', 
                    transform=ax5.transAxes, fontsize=14,
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
        
        # 6. Summary and Results
        ax6 = axes[1, 2]
        ax6.axis('off')
        ax6.set_title('6. Analysis Summary', fontsize=14, fontweight='bold')
        
        # Prepare results
        stm_result = 'buy' if stm_color == 'orange' else 'sell' if stm_color == 'purple' else 'none'
        td_result = 'buy' if td_color == 'yellow' else 'sell' if td_color == 'blue' else 'none'
        hl_result = hl_signal  # Already processed by analyze_horizontal_line_signal
        
        results = {
            "STM": stm_result,
            "TD": td_result,
            "Zigzag": hl_result
        }
        
        # Create summary text with candle details
        candle_details = []
        for i, candle in enumerate(self.candle_positions):
            candle_details.append(f"  C{i+1}: {candle.get('color', '?').upper()} x={candle['center']} (w={candle['width']})")
        
        candle_summary = '\n'.join(candle_details) if candle_details else "  No candles detected"
        
        summary_text = f"""
STRATEGY ANALYSIS RESULTS

CANDLE DETECTION:
• Total candles detected: {len(self.candle_positions)}
• Second rightmost candle: x={candle_x}
• Median candle width: {self.candle_width} pixels

DETECTED CANDLES:
{candle_summary}

📊 SIGNAL ANALYSIS:

STM Signal (Looking Down):
• Colors searched: Orange, Purple
• Result: {stm_result.upper()}
• Details: {f'{len(stm_positions)} {stm_color} pixels found' if stm_color != 'none' else 'No target colors detected'}

TD Signal (Looking Both Ways):
• Colors searched: Yellow, Blue  
• Result: {td_result.upper()}
• Details: {f'{len(td_positions)} {td_color} pixels found' if td_color != 'none' else 'No target colors detected'}

Horizontal Line Signal (Looking Both Ways):
• Colors searched: Aqua, Fuchsia
• Result: {hl_result.upper()}
• Aqua pixels found: {len(aqua_pixels)}
• Fuchsia pixels found: {len(fuchsia_pixels)}
• Validation: 90 pixel horizontal line (45 left + 45 right)

🎯 FINAL JSON OUTPUT:
{json.dumps(results, indent=2)}

📍 COORDINATES:
• Image size: {self.rgb_image.shape[1]} x {self.rgb_image.shape[0]}
• Analysis X-coordinate: {candle_x}
• STM scan range: Y {middle_y}-{self.rgb_image.shape[0]-1}
• TD scan range: Y 0-{self.rgb_image.shape[0]-1}
        """
        
        ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes, fontsize=11,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
        
        # Save the visualization
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f'strategy_visual_analysis_{timestamp}.png'
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        
        print(f"💾 Visual analysis saved to: {output_path}")
        plt.show()
        
        return results, output_path
    
    def run_visual_analysis(self):
        """Run the complete visual strategy analysis."""
        print("🚀 Starting Visual Strategy Analysis")
        print("=" * 60)
        
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
        
        # Create visual analysis
        print("\n" + "=" * 60)
        print("📈 CREATING VISUAL ANALYSIS")
        print("=" * 60)
        
        results, output_path = self.create_visual_analysis(candle_x)
        
        # print(f"\n🎯 FINAL RESULTS:")
        # print(f"STM Signal: {results['STM']}")
        # print(f"TD Signal: {results['TD']}")
        # print(f"Horizontal Line Signal: {results['Zigzag']}")
        print(f"JSON Output: {json.dumps(results)}")
        # print(f"📸 Visual output saved to: {output_path}")
        
        return results

def main():
    """Main function to run the visual strategy analysis."""
    image_path = 'cropped_images/test.png'
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    # Create analyzer
    analyzer = VisualCandleStrategyAnalyzer(image_path)
    
    # Run visual analysis
    results = analyzer.run_visual_analysis()
    
    # Output final JSON
    if "error" not in results:
        print(f"\n🎉 Visual Analysis Complete!")
        print(f"Final JSON: {json.dumps(results)}")
    else:
        print(f"\n❌ Analysis Failed: {results['error']}")

if __name__ == "__main__":
    main()
