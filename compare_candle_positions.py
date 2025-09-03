import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

class CandlePositionComparator:
    def __init__(self, image_path):
        """
        Initialize the candle position comparator.
        
        Args:
            image_path (str): Path to the image file
        """
        self.image_path = image_path
        self.image_array = None
        self.red_pixels = []
        self.green_pixels = []
        
    def load_image(self):
        """Load the image."""
        try:
            # Load with PIL
            self.pil_image = Image.open(self.image_path)
            self.image_array = np.array(self.pil_image)
            
            print(f"Image loaded successfully: {self.image_array.shape}")
            print(f"Image type: {self.image_array.dtype}")
            print(f"Number of channels: {self.image_array.shape[2] if len(self.image_array.shape) > 2 else 1}")
            
            return True
            
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def search_color(self, hex_color):
        """
        Search for a specific hex color in the image.
        
        Args:
            hex_color (str): Hex color code to search for
            
        Returns:
            list: List of (x, y) coordinates of matching pixels
        """
        if self.image_array is None:
            print("Image not loaded")
            return []
        
        # Convert target hex to RGB
        target_rgb = self.hex_to_rgb(hex_color)
        print(f"Searching for color: {hex_color} (RGB: {target_rgb})")
        
        # Handle different image formats
        if len(self.image_array.shape) == 3:
            if self.image_array.shape[2] == 4:  # RGBA
                # Convert RGBA to RGB (ignore alpha channel)
                image_rgb = self.image_array[:, :, :3]
            else:  # RGB
                image_rgb = self.image_array
        else:
            print("Unsupported image format")
            return []
        
        # Find pixels that match the target color exactly
        matching_pixels = []
        
        for y in range(image_rgb.shape[0]):
            for x in range(image_rgb.shape[1]):
                pixel_rgb = tuple(image_rgb[y, x])
                if pixel_rgb == target_rgb:
                    matching_pixels.append((x, y))
        
        print(f"Found {len(matching_pixels)} pixels with color {hex_color}")
        return matching_pixels
    
    def compare_candle_positions(self):
        """
        Search for both red and green candle colors and compare their positions.
        """
        print("Starting candle position comparison...")
        print(f"Target image: {self.image_path}")
        
        # Load image
        if not self.load_image():
            return False
        
        # Search for red candle color
        print("\n" + "="*50)
        print("SEARCHING FOR RED CANDLE")
        print("="*50)
        self.red_pixels = self.search_color("#ea3641")
        
        # Search for green candle color
        print("\n" + "="*50)
        print("SEARCHING FOR GREEN CANDLE")
        print("="*50)
        self.green_pixels = self.search_color("#208d76")
        
        # Compare positions
        print("\n" + "="*50)
        print("POSITION COMPARISON")
        print("="*50)
        
        if not self.red_pixels and not self.green_pixels:
            print("No candles found in the image!")
            return False
        
        if not self.red_pixels:
            print("No red candle found!")
            print("The rightmost is a green candle")
            return "green"
        
        if not self.green_pixels:
            print("No green candle found!")
            print("The rightmost is a red candle")
            return "red"
        
        # Find the rightmost x position for each color
        red_max_x = max(pixel[0] for pixel in self.red_pixels)
        green_max_x = max(pixel[0] for pixel in self.green_pixels)
        
        print(f"Red candle rightmost x position: {red_max_x}")
        print(f"Green candle rightmost x position: {green_max_x}")
        
        if green_max_x > red_max_x:
            result = "The rightmost is a green candle"
            print(result)
        else:
            result = "The rightmost is a red candle"
            print(result)
        
        # Print detailed pixel information
        print(f"\nRed candle pixels found: {len(self.red_pixels)}")
        if self.red_pixels:
            print("Red pixel coordinates (first 5):")
            for i, (x, y) in enumerate(self.red_pixels[:5]):
                print(f"  {i+1}: ({x}, {y})")
        
        print(f"\nGreen candle pixels found: {len(self.green_pixels)}")
        if self.green_pixels:
            print("Green pixel coordinates (first 5):")
            for i, (x, y) in enumerate(self.green_pixels[:5]):
                print(f"  {i+1}: ({x}, {y})")
        
        return result

def main():
    """
    Main function to compare candle positions.
    """
    target_image = 'cropped_images/test.png'
    
    if os.path.exists(target_image):
        print(f"Comparing candle positions in: {target_image}")
        comparator = CandlePositionComparator(target_image)
        result = comparator.compare_candle_positions()
        print(f"\nFinal result: {result}")
    else:
        print(f"Target image '{target_image}' not found.")
        print("Available files in cropped_images/:")
        if os.path.exists('cropped_images'):
            for f in os.listdir('cropped_images'):
                print(f"  - {f}")

if __name__ == "__main__":
    main()
