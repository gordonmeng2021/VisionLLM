import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os
import colorsys

class SpecificColorSearcher:
    def __init__(self, image_path, target_color, tolerance=30):
        """
        Initialize the color searcher.
        
        Args:
            image_path (str): Path to the image file
            target_color (str): Color to search for - can be hex code (e.g., "#b13c3a") or color name (e.g., "purple", "orange")
            tolerance (int): Color matching tolerance (0-100, higher = more lenient matching)
        """
        self.image_path = image_path
        self.target_color = target_color
        self.tolerance = tolerance
        self.image_array = None
        self.matching_pixels = []
        self.color_ranges = self._define_color_ranges()
    
    def _define_color_ranges(self):
        """
        Define color ranges for common color names.
        Returns a dictionary mapping color names to RGB ranges.
        """
        return {
            'red': {
                'hue_range': (0, 20),  # Red hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'orange': {
                'hue_range': (10, 30),  # Orange hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'yellow': {
                'hue_range': (25, 45),  # Yellow hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'green': {
                'hue_range': (60, 140),  # Green hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'blue': {
                'hue_range': (180, 240),  # Blue hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'purple': {
                'hue_range': (260, 300),  # Purple hues
                'saturation_min': 30,
                'saturation_max': 100,
                'value_min': 30,
                'value_max': 100
            },
            'pink': {
                'hue_range': (300, 340),  # Pink hues
                'saturation_min': 20,
                'saturation_max': 100,
                'value_min': 50,
                'value_max': 100
            },
            'brown': {
                'hue_range': (15, 45),  # Brown hues
                'saturation_min': 20,
                'saturation_max': 100,
                'value_min': 20,
                'value_max': 60
            },
            'gray': {
                'saturation_max': 20,  # Low saturation for grays
                'value_min': 20,
                'value_max': 80
            },
            'white': {
                'saturation_max': 20,  # Very low saturation
                'value_min': 80  # High brightness
            },
            'black': {
                'saturation_max': 50,  # Any saturation
                'value_max': 30  # Low brightness
            }
        }
    
    def _is_hex_color(self, color_str):
        """Check if the input is a hex color code."""
        return color_str.startswith('#') and len(color_str) == 7
    
    def _get_color_range(self, color_input):
        """
        Get RGB range for the given color input.
        Returns (min_rgb, max_rgb) tuple or None if color not found.
        """
        if self._is_hex_color(color_input):
            # For hex colors, create a range around the exact color
            base_rgb = self.hex_to_rgb(color_input)
            tolerance = self.tolerance
            
            min_rgb = tuple(max(0, c - tolerance) for c in base_rgb)
            max_rgb = tuple(min(255, c + tolerance) for c in base_rgb)
            
            return min_rgb, max_rgb
        else:
            # For color names, use predefined ranges
            color_name = color_input.lower()
            if color_name in self.color_ranges:
                return self._get_rgb_range_from_hsv(self.color_ranges[color_name])
            else:
                print(f"Unknown color name: {color_name}")
                print(f"Available colors: {list(self.color_ranges.keys())}")
                return None
    
    def _get_rgb_range_from_hsv(self, hsv_range):
        """
        Convert HSV range to RGB range by sampling the HSV space.
        """
        # Sample multiple HSV values within the range and convert to RGB
        rgb_values = []
        
        # Get HSV parameters
        hue_range = hsv_range.get('hue_range', (0, 360))
        sat_min = hsv_range.get('saturation_min', 0)
        sat_max = hsv_range.get('saturation_max', 100)
        val_min = hsv_range.get('value_min', 0)
        val_max = hsv_range.get('value_max', 100)
        
        # Sample HSV values
        hue_start, hue_end = hue_range
        for h in range(hue_start, hue_end + 1, 10):  # Sample every 10 degrees
            for s in range(sat_min, sat_max + 1, 20):  # Sample saturation
                for v in range(val_min, val_max + 1, 20):  # Sample value
                    # Convert HSV to RGB
                    h_norm = h / 360.0
                    s_norm = s / 100.0
                    v_norm = v / 100.0
                    
                    rgb = colorsys.hsv_to_rgb(h_norm, s_norm, v_norm)
                    rgb_int = tuple(int(c * 255) for c in rgb)
                    rgb_values.append(rgb_int)
        
        if not rgb_values:
            # Fallback: create a reasonable range for the color
            return self._get_fallback_rgb_range(hsv_range)
        
        # Find min and max RGB values
        min_r = min(rgb[0] for rgb in rgb_values)
        max_r = max(rgb[0] for rgb in rgb_values)
        min_g = min(rgb[1] for rgb in rgb_values)
        max_g = max(rgb[1] for rgb in rgb_values)
        min_b = min(rgb[2] for rgb in rgb_values)
        max_b = max(rgb[2] for rgb in rgb_values)
        
        # Add tolerance
        tolerance = self.tolerance
        min_rgb = (max(0, min_r - tolerance), max(0, min_g - tolerance), max(0, min_b - tolerance))
        max_rgb = (min(255, max_r + tolerance), min(255, max_g + tolerance), min(255, max_b + tolerance))
        
        return min_rgb, max_rgb
    
    def _get_fallback_rgb_range(self, hsv_range):
        """
        Fallback method to create RGB ranges for special cases like gray, white, black.
        """
        color_type = None
        if 'saturation_max' in hsv_range and hsv_range['saturation_max'] <= 20:
            if hsv_range.get('value_min', 0) >= 80:
                color_type = 'white'
            elif hsv_range.get('value_max', 100) <= 30:
                color_type = 'black'
            else:
                color_type = 'gray'
        
        if color_type == 'white':
            return (200, 200, 200), (255, 255, 255)
        elif color_type == 'black':
            return (0, 0, 0), (50, 50, 50)
        elif color_type == 'gray':
            return (50, 50, 50), (200, 200, 200)
        else:
            # Generic fallback
            return (0, 0, 0), (255, 255, 255)
        
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
    
    def search_color_range(self):
        """
        Search for colors within the specified range in the image.
        """
        if self.image_array is None:
            print("Image not loaded")
            return []
        
        # Get color range
        color_range = self._get_color_range(self.target_color)
        if color_range is None:
            print(f"Could not determine color range for: {self.target_color}")
            return []
        
        min_rgb, max_rgb = color_range
        print(f"Searching for color: {self.target_color}")
        print(f"RGB range: {min_rgb} to {max_rgb}")
        print(f"Tolerance: {self.tolerance}")
        
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
        
        # Find pixels that fall within the color range
        self.matching_pixels = []
        
        for y in range(image_rgb.shape[0]):
            for x in range(image_rgb.shape[1]):
                pixel_rgb = tuple(image_rgb[y, x])
                if self._is_color_in_range(pixel_rgb, min_rgb, max_rgb):
                    self.matching_pixels.append((x, y))
        
        print(f"Found {len(self.matching_pixels)} pixels with color {self.target_color}")
        return self.matching_pixels
    
    def _is_color_in_range(self, pixel_rgb, min_rgb, max_rgb):
        """
        Check if a pixel RGB value falls within the specified range.
        """
        r, g, b = pixel_rgb
        min_r, min_g, min_b = min_rgb
        max_r, max_g, max_b = max_rgb
        
        return (min_r <= r <= max_r and 
                min_g <= g <= max_g and 
                min_b <= b <= max_b)
    
    def plot_matching_pixels(self):
        """
        Plot the image with matching pixels highlighted.
        """
        if not self.matching_pixels:
            print("No matching pixels found to plot")
            return None
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
        
        # Original image
        ax1.imshow(self.image_array[:, :, :3] if len(self.image_array.shape) == 3 else self.image_array)
        ax1.set_title('Original Image')
        ax1.axis('off')
        
        # Image with matching pixels highlighted
        ax2.imshow(self.image_array[:, :, :3] if len(self.image_array.shape) == 3 else self.image_array)
        
        # Mark matching pixels with bright yellow circles for visibility
        for x, y in self.matching_pixels:
            circle = plt.Circle((x, y), 3, color='yellow', fill=False, linewidth=2)
            ax2.add_patch(circle)
        
        ax2.set_title(f'Pixels with color {self.target_color} ({len(self.matching_pixels)} pixels)')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save the result
        color_name = self.target_color.replace('#', '').replace(' ', '_')
        output_path = f'color_search_{color_name}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Search results saved to: {output_path}")
        
        plt.show()
        
        return output_path
    
    def analyze_color_range(self):
        """
        Main method to search for colors within the specified range.
        """
        print("Starting color range search...")
        print(f"Target image: {self.image_path}")
        print(f"Target color: {self.target_color}")
        print(f"Tolerance: {self.tolerance}")
        
        # Load image
        if not self.load_image():
            return False
        
        # Search for colors in the range
        self.search_color_range()
        
        # Plot and save results
        output_path = self.plot_matching_pixels()
        
        # Print summary
        print("\n" + "="*60)
        print("COLOR RANGE SEARCH SUMMARY")
        print("="*60)
        print(f"Image: {self.image_path}")
        print(f"Image dimensions: {self.image_array.shape}")
        print(f"Target color: {self.target_color}")
        print(f"Tolerance: {self.tolerance}")
        print(f"Matching pixels found: {len(self.matching_pixels)}")
        
        if self.matching_pixels:
            print("Matching pixel coordinates (x, y):")
            for i, (x, y) in enumerate(self.matching_pixels[:10]):  # Show first 10
                print(f"  {i+1}: ({x}, {y})")
            if len(self.matching_pixels) > 10:
                print(f"  ... and {len(self.matching_pixels) - 10} more")
        
        if output_path:
            print(f"Result saved to: {output_path}")
        print("="*60)
        
        return True

def main():
    """
    Main function to search for colors (hex codes or color names).
    """
    target_image = 'cropped_images/test.png'
    
    # Examples of different color inputs:
    # target_color = "#ea3641"  # Hex color with tolerance
    # target_color = "purple"   # Color name
    # target_color = "orange"   # Color name
    target_color = "purple"  # You can change this to any color name or hex code
    tolerance = 1  # Adjust tolerance (0-100, higher = more lenient)
    
    if os.path.exists(target_image):
        print(f"Searching for color '{target_color}' in: {target_image}")
        searcher = SpecificColorSearcher(target_image, target_color, tolerance)
        searcher.analyze_color_range()
    else:
        print(f"Target image '{target_image}' not found.")
        print("Available files in cropped_images/:")
        if os.path.exists('cropped_images'):
            for f in os.listdir('cropped_images'):
                print(f"  - {f}")
        
        print("\nAvailable color names:")
        searcher = SpecificColorSearcher("", "", 0)  # Dummy instance to get color names
        for color in searcher.color_ranges.keys():
            print(f"  - {color}")

if __name__ == "__main__":
    main()
