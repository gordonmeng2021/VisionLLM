#!/usr/bin/env python3
"""
Green Color Detector
Detects green colors in images using precise RGB analysis.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from color_detection_tools.unified_color_detector import UnifiedColorDetector

def main():
    """Detect green colors in the test image."""
    target_image = 'cropped_images/test.png'
    
    if not os.path.exists(target_image):
        print(f"❌ Target image '{target_image}' not found.")
        return
    
    print("🟢 GREEN COLOR DETECTION")
    print("=" * 50)
    
    # Create detector
    detector = UnifiedColorDetector(target_image)
    
    # Load image and analyze
    if not detector.load_image():
        return
    
    detector.analyze_unique_colors()
    
    # Detect green colors
    result = detector.analyze_color('green')
    
    if result['success']:
        print(f"\n🎉 Green detection complete!")
        print(f"📁 Results saved in: color_analysis_results/")
    else:
        print(f"\n❌ No green colors found in the image.")

if __name__ == "__main__":
    main()
