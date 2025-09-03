import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

def search_color_in_image(image_path, hex_color):
    """
    Search for a specific hex color in an image and return results.
    
    Args:
        image_path (str): Path to the image file
        hex_color (str): Hex color code to search for (e.g., "#b13c3a")
    
    Returns:
        dict: Results containing pixel count and coordinates
    """
    # Load image
    try:
        pil_image = Image.open(image_path)
        image_array = np.array(pil_image)
        print(f"Image loaded: {image_array.shape}")
    except Exception as e:
        print(f"Error loading image: {e}")
        return None
    
    # Convert hex to RGB
    hex_color = hex_color.upper().lstrip('#')
    target_rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    print(f"Searching for: #{hex_color} (RGB: {target_rgb})")
    
    # Handle different image formats
    if len(image_array.shape) == 3:
        if image_array.shape[2] == 4:  # RGBA
            image_rgb = image_array[:, :, :3]
        else:  # RGB
            image_rgb = image_array
    else:
        print("Unsupported image format")
        return None
    
    # Find matching pixels
    matching_pixels = []
    for y in range(image_rgb.shape[0]):
        for x in range(image_rgb.shape[1]):
            pixel_rgb = tuple(image_rgb[y, x])
            if pixel_rgb == target_rgb:
                matching_pixels.append((x, y))
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
    
    # Original image
    ax1.imshow(image_rgb)
    ax1.set_title('Original Image')
    ax1.axis('off')
    
    # Image with matching pixels highlighted
    ax2.imshow(image_rgb)
    
    # Mark matching pixels
    for x, y in matching_pixels:
        circle = plt.Circle((x, y), 2, color='yellow', fill=False, linewidth=1.5)
        ax2.add_patch(circle)
    
    ax2.set_title(f'Color #{hex_color} Found ({len(matching_pixels)} pixels)')
    ax2.axis('off')
    
    plt.tight_layout()
    
    # Save result
    output_path = f'search_{hex_color}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Results saved to: {output_path}")
    
    plt.show()
    
    return {
        'color': f"#{hex_color}",
        'rgb': target_rgb,
        'pixel_count': len(matching_pixels),
        'coordinates': matching_pixels,
        'output_file': output_path
    }

def main():
    """
    Interactive color search tool.
    """
    image_path = 'cropped_images/test.png'
    
    if not os.path.exists(image_path):
        print(f"Image '{image_path}' not found.")
        return
    
    print("="*60)
    print("SPECIFIC COLOR SEARCH TOOL")
    print("="*60)
    print(f"Image: {image_path}")
    print("Available hex colors from previous analysis:")
    print("  - #720C0C (dark red, 3,477 pixels)")
    print("  - #B13C3A (medium red, 1,639 pixels)")
    print("  - #EA3641 (bright red, 800 pixels)")
    print("  - #FB8F2A (orange-red, 632 pixels)")
    print("  - #A52830 (dark red, 264 pixels)")
    print("="*60)
    
    # You can change this hex color to search for different colors
    target_colors = [
        "#B13C3A",  # The one you specified
        "#720C0C",  # Most frequent red
        "#EA3641",  # Bright red
        "#FB8F2A",  # Orange-red
        "#A52830"   # Dark red
    ]
    
    for hex_color in target_colors:
        print(f"\nSearching for color: {hex_color}")
        result = search_color_in_image(image_path, hex_color)
        
        if result:
            print(f"✅ Found {result['pixel_count']} pixels with color {result['color']}")
            print(f"   RGB: {result['rgb']}")
            print(f"   Saved to: {result['output_file']}")
        else:
            print(f"❌ No pixels found with color {hex_color}")
        
        print("-" * 40)

if __name__ == "__main__":
    main()
