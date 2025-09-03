from PIL import Image
import os

def crop_image(image_path, output_dir="cropped_images"):
    """
    Crop specific regions from an image with hardcoded coordinates.
    Easy to adjust x, y positions for testing different crop areas.
    """
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Load the image
    try:
        img = Image.open(image_path)
        print(f"Original image size: {img.size} (width x height)")
    except Exception as e:
        print(f"Error loading image: {e}")
        return
    
    # CROP 1: Small top left corner
    # Adjust these coordinates as needed
    top_left_x = 160          # Starting x position (left edge)
    top_left_y = 0         # Starting y position (top edge)
    top_left_width = 140  # Width of the crop
    top_left_height = 60   # Height of the crop
    
    # CROP 2: Vertical long rectangle in the middle-right area
    # Adjust these coordinates as needed
    vertical_x = 2500        # Starting x position (from left)
    vertical_y = 80         # Starting y position (from top)
    vertical_width = 250    # Width of the vertical rectangle
    vertical_height = 1430   # Height of the vertical rectangle
    
    # Perform the crops
    crops = []
    
    # Crop 1: Top left corner
    try:
        top_left_crop = img.crop((
            top_left_x, 
            top_left_y, 
            top_left_x + top_left_width, 
            top_left_y + top_left_height
        ))
        
        top_left_path = os.path.join(output_dir, "top_left_corner.png")
        top_left_crop.save(top_left_path)
        crops.append(("Top Left Corner", top_left_path, top_left_crop.size))
        print(f"✓ Top left corner saved: {top_left_path}")
        print(f"  Crop area: ({top_left_x}, {top_left_y}) to ({top_left_x + top_left_width}, {top_left_y + top_left_height})")
        
    except Exception as e:
        print(f"Error cropping top left: {e}")
    
    # Crop 2: Vertical rectangle
    try:
        vertical_crop = img.crop((
            vertical_x, 
            vertical_y, 
            vertical_x + vertical_width, 
            vertical_y + vertical_height
        ))
        
        vertical_path = os.path.join(output_dir, "vertical_rectangle.png")
        vertical_crop.save(vertical_path)
        crops.append(("Vertical Rectangle", vertical_path, vertical_crop.size))
        print(f"✓ Vertical rectangle saved: {vertical_path}")
        print(f"  Crop area: ({vertical_x}, {vertical_y}) to ({vertical_x + vertical_width}, {vertical_y + vertical_height})")
        
    except Exception as e:
        print(f"Error cropping vertical rectangle: {e}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"Original image: {img.size[0]}x{img.size[1]} pixels")
    for name, path, size in crops:
        print(f"{name}: {size[0]}x{size[1]} pixels")
    
    return crops

def preview_crop_coordinates(image_path):
    """
    Show the current crop coordinates and image dimensions for easy adjustment.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        print(f"🖼️  Image: {image_path}")
        print(f"📏 Dimensions: {width} x {height} pixels")
        print(f"\n📐 Current Crop Coordinates:")
        print(f"Top Left Corner:")
        print(f"  x: 0 to 200 (width: 200)")
        print(f"  y: 0 to 150 (height: 150)")
        print(f"\nVertical Rectangle:")
        print(f"  x: 400 to 500 (width: 100)")
        print(f"  y: 50 to 650 (height: 600)")
        print(f"\n💡 To adjust coordinates, modify the variables in the crop_image() function")
        
    except Exception as e:
        print(f"Error loading image: {e}")

if __name__ == "__main__":
    # Set your image path here
    image_path = "test.png"
    
    # Preview current coordinates
    print("=" * 50)
    preview_crop_coordinates(image_path)
    print("=" * 50)
    
    # Perform the cropping
    print("\n🔄 Starting crop operation...")
    crops = crop_image(image_path)
    
    print(f"\n✅ Cropping complete! Check the 'cropped_images' folder for results.")
