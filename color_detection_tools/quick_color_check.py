#!/usr/bin/env python3
"""
Quick Color Check
A simple script to quickly check what colors are present in an image.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from color_detection_tools.unified_color_detector import UnifiedColorDetector

def main():
    """Quick color check for the test image."""
    target_image = 'cropped_images/test.png'
    
    if not os.path.exists(target_image):
        print(f"❌ Target image '{target_image}' not found.")
        return
    
    print("🎨 QUICK COLOR CHECK")
    print("=" * 50)
    
    # Create detector
    detector = UnifiedColorDetector(target_image)
    
    # Load image and analyze
    if not detector.load_image():
        return
    
    detector.analyze_unique_colors()
    
    # Quick check for each color
    colors_to_check = ['purple', 'blue', 'yellow', 'orange']
    results = {}
    
    for color in colors_to_check:
        detected_colors = detector.detect_color(color)
        if detected_colors:
            total_pixels = sum(count for _, count in detected_colors)
            results[color] = total_pixels
        else:
            results[color] = 0
    
    # Print summary
    print(f"\n📊 QUICK SUMMARY:")
    print("-" * 30)
    for color, count in results.items():
        if count > 0:
            percentage = (count / (detector.rgb_image.shape[0] * detector.rgb_image.shape[1])) * 100
            print(f"✅ {color.title()}: {count:,} pixels ({percentage:.2f}%)")
        else:
            print(f"❌ {color.title()}: No pixels found")
    
    print(f"\n💡 For detailed analysis, run:")
    print(f"   python color_detection_tools/unified_color_detector.py")

if __name__ == "__main__":
    main()
