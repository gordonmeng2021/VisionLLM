#!/usr/bin/env python3
"""
Aqua Color Detector
Detects aqua/cyan colors in images using precise RGB analysis.
Distinguishes aqua from pure blue by requiring significant green component.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from color_detection_tools.unified_color_detector import UnifiedColorDetector

def main():
    """Detect aqua colors in the test image."""
    target_image = 'cropped_images/test.png'
    
    if not os.path.exists(target_image):
        print(f"❌ Target image '{target_image}' not found.")
        return
    
    print("🔵💚 AQUA COLOR DETECTION")
    print("=" * 50)
    print("🎯 Detecting cyan/aqua colors (high blue + green, low red)")
    print("📝 This detector distinguishes aqua from pure blue colors")
    print("=" * 50)
    
    # Create detector
    detector = UnifiedColorDetector(target_image)
    
    # Load image and analyze
    if not detector.load_image():
        return
    
    detector.analyze_unique_colors()
    
    # Detect aqua colors
    result = detector.analyze_color('aqua')
    
    if result['success']:
        print(f"\n🎉 Aqua detection complete!")
        print(f"📁 Results saved in: color_analysis_results/")
        print(f"🔍 Check the visualization to see detected aqua pixels highlighted")
    else:
        print(f"\n❌ No aqua colors found in the image.")
        print(f"💡 Aqua colors require high blue AND green components with low red")

if __name__ == "__main__":
    main()
