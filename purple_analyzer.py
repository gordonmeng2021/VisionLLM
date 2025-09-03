import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

def analyze_purple_pixels_in_image(image_path):
    """
    Analyze the actual purple pixels in the image to understand their HSV values.
    """
    print("="*60)
    print("PURPLE PIXEL ANALYSIS")
    print("="*60)
    
    # Load image
    try:
        pil_image = Image.open(image_path)
        image_array = np.array(pil_image)
        print(f"Image loaded: {image_array.shape}")
    except Exception as e:
        print(f"Error loading image: {e}")
        return
    
    # Convert to RGB and HSV
    if len(image_array.shape) == 3:
        if image_array.shape[2] == 4:  # RGBA
            rgb_image = image_array[:, :, :3]
        else:  # RGB
            rgb_image = image_array
        
        hsv_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2HSV)
        print(f"HSV image shape: {hsv_image.shape}")
    else:
        print("Unsupported image format")
        return
    
    # Use the original broad purple detection to find potential purple pixels
    # This is based on your original code that found 8806 pixels
    purple_ranges = [
        # Very broad purple range to catch all potential purples
        {
            'hue_min': 250, 'hue_max': 320,  # Very broad hue range
            'sat_min': 20, 'sat_max': 100,   # Any saturation
            'val_min': 10, 'val_max': 100    # Any brightness
        }
    ]
    
    potential_purple_pixels = []
    
    for y in range(hsv_image.shape[0]):
        for x in range(hsv_image.shape[1]):
            h, s, v = hsv_image[y, x]
            
            # Check against broad purple range
            for purple_range in purple_ranges:
                hue_min = purple_range['hue_min']
                hue_max = purple_range['hue_max']
                
                if hue_min <= hue_max:
                    hue_match = hue_min <= h <= hue_max
                else:
                    hue_match = h >= hue_min or h <= hue_max
                
                sat_match = purple_range['sat_min'] <= s <= purple_range['sat_max']
                val_match = purple_range['val_min'] <= v <= purple_range['val_max']
                
                if hue_match and sat_match and val_match:
                    potential_purple_pixels.append((x, y, h, s, v))
                    break
    
    print(f"Found {len(potential_purple_pixels)} potential purple pixels")
    
    if potential_purple_pixels:
        # Analyze the HSV values
        hues = [p[2] for p in potential_purple_pixels]
        sats = [p[3] for p in potential_purple_pixels]
        vals = [p[4] for p in potential_purple_pixels]
        
        print(f"\nHSV Statistics:")
        print(f"Hue - Min: {min(hues)}, Max: {max(hues)}, Mean: {np.mean(hues):.1f}")
        print(f"Sat - Min: {min(sats)}, Max: {max(sats)}, Mean: {np.mean(sats):.1f}")
        print(f"Val - Min: {min(vals)}, Max: {max(vals)}, Mean: {np.mean(vals):.1f}")
        
        # Show some examples
        print(f"\nFirst 20 potential purple pixels (x, y, h, s, v):")
        for i, (x, y, h, s, v) in enumerate(potential_purple_pixels[:20]):
            rgb_val = rgb_image[y, x]
            print(f"  {i+1:2d}: ({x:3d}, {y:3d}) HSV:({h:3d}, {s:3d}, {v:3d}) RGB:({rgb_val[0]:3d}, {rgb_val[1]:3d}, {rgb_val[2]:3d})")
        
        # Create visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Original image
        ax1.imshow(rgb_image)
        ax1.set_title('Original Image')
        ax1.axis('off')
        
        # Highlight potential purple pixels
        overlay_image = rgb_image.copy()
        for x, y, h, s, v in potential_purple_pixels:
            overlay_image[y, x] = [255, 255, 0]  # Yellow
        
        ax2.imshow(overlay_image)
        ax2.set_title(f'Potential Purple Pixels ({len(potential_purple_pixels)} pixels)')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save result
        output_path = 'purple_analysis.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\nAnalysis saved to: {output_path}")
        
        plt.show()
        
        # Suggest improved ranges
        print(f"\n" + "="*60)
        print("SUGGESTED IMPROVED PURPLE RANGES")
        print("="*60)
        
        # Calculate ranges with some margin
        hue_margin = 10
        sat_margin = 10
        val_margin = 10
        
        suggested_hue_min = max(0, min(hues) - hue_margin)
        suggested_hue_max = min(360, max(hues) + hue_margin)
        suggested_sat_min = max(0, min(sats) - sat_margin)
        suggested_sat_max = min(100, max(sats) + sat_margin)
        suggested_val_min = max(0, min(vals) - val_margin)
        suggested_val_max = min(100, max(vals) + val_margin)
        
        print(f"Suggested HSV ranges:")
        print(f"  Hue: {suggested_hue_min} - {suggested_hue_max}")
        print(f"  Sat: {suggested_sat_min} - {suggested_sat_max}")
        print(f"  Val: {suggested_val_min} - {suggested_val_max}")
        
        # Create code snippet
        print(f"\nCode snippet for improved ranges:")
        print(f"purple_hsv_ranges = [")
        print(f"    {{")
        print(f"        'hue_min': {suggested_hue_min}, 'hue_max': {suggested_hue_max},")
        print(f"        'sat_min': {suggested_sat_min}, 'sat_max': {suggested_sat_max},")
        print(f"        'val_min': {suggested_val_min}, 'val_max': {suggested_val_max}")
        print(f"    }}")
        print(f"]")
        
    else:
        print("No potential purple pixels found with broad criteria")

def main():
    target_image = 'cropped_images/test.png'
    
    if os.path.exists(target_image):
        analyze_purple_pixels_in_image(target_image)
    else:
        print(f"Target image '{target_image}' not found.")

if __name__ == "__main__":
    main()
