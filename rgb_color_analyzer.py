import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os
from collections import Counter

def analyze_rgb_colors_in_image(image_path):
    """
    Analyze RGB colors in the image to understand what colors are actually present.
    """
    print("="*60)
    print("RGB COLOR ANALYSIS")
    print("="*60)
    
    # Load image
    try:
        pil_image = Image.open(image_path)
        image_array = np.array(pil_image)
        print(f"Image loaded: {image_array.shape}")
    except Exception as e:
        print(f"Error loading image: {e}")
        return
    
    # Convert to RGB
    if len(image_array.shape) == 3:
        if image_array.shape[2] == 4:  # RGBA
            rgb_image = image_array[:, :, :3]
        else:  # RGB
            rgb_image = image_array
    else:
        print("Unsupported image format")
        return
    
    print(f"RGB image shape: {rgb_image.shape}")
    
    # Analyze unique colors
    print("Analyzing unique colors...")
    
    # Reshape to get all pixels
    pixels = rgb_image.reshape(-1, 3)
    print(f"Total pixels: {len(pixels)}")
    
    # Count unique colors
    unique_colors = {}
    for pixel in pixels:
        pixel_tuple = tuple(pixel)
        unique_colors[pixel_tuple] = unique_colors.get(pixel_tuple, 0) + 1
    
    print(f"Unique colors found: {len(unique_colors)}")
    
    # Sort by frequency
    sorted_colors = sorted(unique_colors.items(), key=lambda x: x[1], reverse=True)
    
    # Show top 20 most frequent colors
    print(f"\nTop 20 most frequent colors (RGB, count):")
    for i, ((r, g, b), count) in enumerate(sorted_colors[:20]):
        percentage = (count / len(pixels)) * 100
        print(f"  {i+1:2d}: RGB({r:3d}, {g:3d}, {b:3d}) - {count:6d} pixels ({percentage:5.2f}%)")
    
    # Look for colors that might be considered "purple" based on RGB
    print(f"\n" + "="*60)
    print("POTENTIAL PURPLE COLORS (RGB-based)")
    print("="*60)
    
    potential_purples = []
    
    for (r, g, b), count in sorted_colors:
        # Purple characteristics in RGB:
        # 1. Blue should be significant
        # 2. Red should be present
        # 3. Green should be relatively low
        # 4. Should have some color (not too gray)
        
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        
        # Check if it could be purple
        is_potential_purple = False
        
        # Rule 1: Blue should be significant (at least 70% of max component)
        if b >= max_val * 0.7:
            # Rule 2: Green should be lower than both R and B
            if g < r and g < b:
                # Rule 3: Should have some color variation
                if max_val - min_val > 20:
                    # Rule 4: Red should be present (not just blue)
                    if r > 20:
                        is_potential_purple = True
        
        if is_potential_purple:
            potential_purples.append(((r, g, b), count))
    
    if potential_purples:
        print(f"Found {len(potential_purples)} potential purple colors:")
        total_purple_pixels = 0
        
        for i, ((r, g, b), count) in enumerate(potential_purples):
            percentage = (count / len(pixels)) * 100
            total_purple_pixels += count
            print(f"  {i+1:2d}: RGB({r:3d}, {g:3d}, {b:3d}) - {count:6d} pixels ({percentage:5.2f}%)")
        
        print(f"\nTotal potential purple pixels: {total_purple_pixels}")
        print(f"Percentage of image: {(total_purple_pixels / len(pixels)) * 100:.2f}%")
        
        # Create visualization
        create_purple_visualization(rgb_image, potential_purples)
        
    else:
        print("No potential purple colors found based on RGB analysis")
    
    # Also check for colors that might be misidentified as purple
    print(f"\n" + "="*60)
    print("COLORS THAT MIGHT BE MISIDENTIFIED AS PURPLE")
    print("="*60)
    
    misidentified = []
    for (r, g, b), count in sorted_colors[:50]:  # Check top 50 colors
        # Colors that have high blue but might not be purple
        if b > max(r, g) * 0.8 and count > 100:  # High blue component
            if not (g < r and g < b):  # But green is not low
                misidentified.append(((r, g, b), count))
    
    if misidentified:
        print("Colors with high blue that might be misidentified:")
        for i, ((r, g, b), count) in enumerate(misidentified[:10]):
            percentage = (count / len(pixels)) * 100
            print(f"  {i+1:2d}: RGB({r:3d}, {g:3d}, {b:3d}) - {count:6d} pixels ({percentage:5.2f}%)")

def create_purple_visualization(rgb_image, potential_purples):
    """
    Create visualization showing potential purple pixels.
    """
    # Create mask for potential purple pixels
    purple_mask = np.zeros(rgb_image.shape[:2], dtype=bool)
    
    # Get the RGB values of potential purples
    purple_rgb_values = [rgb for (rgb, count) in potential_purples]
    
    # Create mask
    for y in range(rgb_image.shape[0]):
        for x in range(rgb_image.shape[1]):
            pixel_rgb = tuple(rgb_image[y, x])
            if pixel_rgb in purple_rgb_values:
                purple_mask[y, x] = True
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # Original image
    ax1.imshow(rgb_image)
    ax1.set_title('Original Image')
    ax1.axis('off')
    
    # Highlight potential purple pixels
    overlay_image = rgb_image.copy()
    purple_pixels = np.where(purple_mask)
    overlay_image[purple_pixels] = [255, 255, 0]  # Yellow
    
    ax2.imshow(overlay_image)
    ax2.set_title(f'Potential Purple Pixels (RGB-based)')
    ax2.axis('off')
    
    plt.tight_layout()
    
    # Save result
    output_path = 'rgb_purple_analysis.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nRGB-based purple analysis saved to: {output_path}")
    
    plt.show()

def main():
    target_image = 'cropped_images/test.png'
    
    if os.path.exists(target_image):
        analyze_rgb_colors_in_image(target_image)
    else:
        print(f"Target image '{target_image}' not found.")

if __name__ == "__main__":
    main()
