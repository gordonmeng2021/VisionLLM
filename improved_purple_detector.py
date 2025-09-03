import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os
import colorsys

class ImprovedPurpleDetector:
    def __init__(self, image_path, tolerance=15):
        """
        Initialize the improved purple detector with precise HSV-based detection.
        
        Args:
            image_path (str): Path to the image file
            tolerance (int): HSV tolerance for color matching (0-50, lower = more precise)
        """
        self.image_path = image_path
        self.tolerance = tolerance
        self.image_array = None
        self.matching_pixels = []
        
        # Define precise purple ranges in HSV
        self.purple_hsv_ranges = [
            # Primary purple range (magenta to violet)
            {
                'hue_min': 260, 'hue_max': 300,  # Purple hues
                'sat_min': 40, 'sat_max': 100,   # Good saturation
                'val_min': 30, 'val_max': 100    # Reasonable brightness
            },
            # Secondary purple range (deeper purples)
            {
                'hue_min': 280, 'hue_max': 320,  # Slightly shifted
                'sat_min': 30, 'sat_max': 90,    # Lower saturation for deeper purples
                'val_min': 20, 'val_max': 80     # Lower brightness for deeper purples
            }
        ]
    
    def load_image(self):
        """Load the image and convert to HSV."""
        try:
            # Load with PIL
            self.pil_image = Image.open(self.image_path)
            self.image_array = np.array(self.pil_image)
            
            print(f"Image loaded successfully: {self.image_array.shape}")
            print(f"Image type: {self.image_array.dtype}")
            print(f"Number of channels: {self.image_array.shape[2] if len(self.image_array.shape) > 2 else 1}")
            
            # Convert to HSV for better color detection
            if len(self.image_array.shape) == 3:
                if self.image_array.shape[2] == 4:  # RGBA
                    # Convert RGBA to RGB first
                    rgb_image = self.image_array[:, :, :3]
                else:  # RGB
                    rgb_image = self.image_array
                
                # Convert RGB to HSV
                self.hsv_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2HSV)
                self.rgb_image = rgb_image
                
                print(f"HSV image shape: {self.hsv_image.shape}")
                return True
            else:
                print("Unsupported image format")
                return False
                
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def is_purple_pixel(self, hsv_pixel):
        """
        Check if a pixel is purple using precise HSV criteria.
        
        Args:
            hsv_pixel: HSV pixel values (h, s, v)
        
        Returns:
            bool: True if pixel is purple
        """
        h, s, v = hsv_pixel
        
        # Check against all purple ranges
        for purple_range in self.purple_hsv_ranges:
            # Check hue (handle wraparound for red-purple transition)
            hue_min = purple_range['hue_min']
            hue_max = purple_range['hue_max']
            
            if hue_min <= hue_max:
                # Normal range
                hue_match = hue_min <= h <= hue_max
            else:
                # Wraparound range (e.g., 350-10)
                hue_match = h >= hue_min or h <= hue_max
            
            # Check saturation and value
            sat_match = purple_range['sat_min'] <= s <= purple_range['sat_max']
            val_match = purple_range['val_min'] <= v <= purple_range['val_max']
            
            if hue_match and sat_match and val_match:
                return True
        
        return False
    
    def validate_purple_pixel(self, rgb_pixel):
        """
        Additional validation to ensure the pixel is actually purple.
        This helps filter out false positives.
        
        Args:
            rgb_pixel: RGB pixel values (r, g, b)
        
        Returns:
            bool: True if pixel passes purple validation
        """
        r, g, b = rgb_pixel
        
        # Purple should have:
        # 1. Blue component should be significant
        # 2. Red component should be present but not dominant
        # 3. Green component should be low (purple = red + blue, minimal green)
        
        # Check that blue is the dominant component or at least significant
        if b < max(r, g) * 0.7:  # Blue should be at least 70% of the max component
            return False
        
        # Check that green is not too high (purple shouldn't have much green)
        if g > min(r, b) * 0.8:  # Green shouldn't be more than 80% of the smaller of R or B
            return False
        
        # Check that it's not too gray (should have some color)
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        if max_val - min_val < 30:  # Too little color variation
            return False
        
        return True
    
    def detect_purple_pixels(self):
        """
        Detect purple pixels using improved HSV-based detection with validation.
        """
        if self.image_array is None:
            print("Image not loaded")
            return []
        
        print("Starting improved purple detection...")
        print(f"Using {len(self.purple_hsv_ranges)} purple HSV ranges")
        print(f"Tolerance: {self.tolerance}")
        
        self.matching_pixels = []
        total_pixels = self.hsv_image.shape[0] * self.hsv_image.shape[1]
        checked_pixels = 0
        
        for y in range(self.hsv_image.shape[0]):
            for x in range(self.hsv_image.shape[1]):
                checked_pixels += 1
                
                # Get HSV and RGB values
                hsv_pixel = self.hsv_image[y, x]
                rgb_pixel = self.rgb_image[y, x]
                
                # Check if pixel is purple using HSV
                if self.is_purple_pixel(hsv_pixel):
                    # Additional RGB validation
                    if self.validate_purple_pixel(rgb_pixel):
                        self.matching_pixels.append((x, y))
                
                # Progress indicator
                if checked_pixels % (total_pixels // 10) == 0:
                    progress = (checked_pixels / total_pixels) * 100
                    print(f"Progress: {progress:.1f}% - Found {len(self.matching_pixels)} purple pixels so far")
        
        print(f"Detection complete! Found {len(self.matching_pixels)} purple pixels")
        return self.matching_pixels
    
    def create_visualization(self):
        """
        Create visualization with yellow masking for manual checking.
        """
        if not self.matching_pixels:
            print("No purple pixels found to visualize")
            return None
        
        # Create figure with side-by-side comparison
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Original image
        ax1.imshow(self.rgb_image)
        ax1.set_title('Original Image')
        ax1.axis('off')
        
        # Create mask image with yellow highlighting
        mask_image = np.zeros_like(self.rgb_image)
        
        # Fill matching pixels with bright yellow for visibility
        for x, y in self.matching_pixels:
            mask_image[y, x] = [255, 255, 0]  # Bright yellow
        
        # Overlay mask on original image
        overlay_image = self.rgb_image.copy()
        for x, y in self.matching_pixels:
            overlay_image[y, x] = [255, 255, 0]  # Yellow
        
        ax2.imshow(overlay_image)
        ax2.set_title(f'Purple Pixels Detected ({len(self.matching_pixels)} pixels)')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save the result
        output_path = f'improved_purple_detection_{len(self.matching_pixels)}_pixels.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to: {output_path}")
        
        plt.show()
        
        return output_path
    
    def analyze_purple_pixels(self):
        """
        Main method to detect and analyze purple pixels.
        """
        print("="*60)
        print("IMPROVED PURPLE DETECTION")
        print("="*60)
        print(f"Target image: {self.image_path}")
        print(f"Tolerance: {self.tolerance}")
        
        # Load image
        if not self.load_image():
            return False
        
        # Detect purple pixels
        self.detect_purple_pixels()
        
        # Create visualization
        output_path = self.create_visualization()
        
        # Print detailed summary
        print("\n" + "="*60)
        print("PURPLE DETECTION SUMMARY")
        print("="*60)
        print(f"Image: {self.image_path}")
        print(f"Image dimensions: {self.image_array.shape}")
        print(f"Total pixels analyzed: {self.hsv_image.shape[0] * self.hsv_image.shape[1]}")
        print(f"Purple pixels found: {len(self.matching_pixels)}")
        print(f"Detection percentage: {(len(self.matching_pixels) / (self.hsv_image.shape[0] * self.hsv_image.shape[1])) * 100:.2f}%")
        
        if self.matching_pixels:
            print("\nPurple pixel coordinates (x, y) - First 20:")
            for i, (x, y) in enumerate(self.matching_pixels[:20]):
                hsv_val = self.hsv_image[y, x]
                rgb_val = self.rgb_image[y, x]
                print(f"  {i+1:2d}: ({x:3d}, {y:3d}) - HSV:({hsv_val[0]:3d}, {hsv_val[1]:3d}, {hsv_val[2]:3d}) RGB:({rgb_val[0]:3d}, {rgb_val[1]:3d}, {rgb_val[2]:3d})")
            
            if len(self.matching_pixels) > 20:
                print(f"  ... and {len(self.matching_pixels) - 20} more purple pixels")
        
        if output_path:
            print(f"\nResult saved to: {output_path}")
        
        print("="*60)
        
        return True

def main():
    """
    Main function to run improved purple detection.
    """
    target_image = 'cropped_images/test.png'
    tolerance = 15  # Adjust tolerance (0-50, lower = more precise)
    
    if os.path.exists(target_image):
        print(f"Running improved purple detection on: {target_image}")
        detector = ImprovedPurpleDetector(target_image, tolerance)
        detector.analyze_purple_pixels()
    else:
        print(f"Target image '{target_image}' not found.")
        print("Available files in cropped_images/:")
        if os.path.exists('cropped_images'):
            for f in os.listdir('cropped_images'):
                print(f"  - {f}")

if __name__ == "__main__":
    main()
