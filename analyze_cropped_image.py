import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

class CroppedImageAnalyzer:
    def __init__(self, image_path):
        """
        Initialize the analyzer for the cropped image.
        
        Args:
            image_path (str): Path to the cropped image file
        """
        self.image_path = image_path
        self.image = None
        self.image_array = None
        self.red_pixels = []
        
    def load_image(self):
        """Load the cropped image."""
        try:
            # Load with OpenCV (BGR format)
            self.image = cv2.imread(self.image_path)
            if self.image is None:
                raise ValueError(f"Could not load image from {self.image_path}")
            
            # Convert to RGB for matplotlib
            self.image_rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
            
            # Load with PIL for easier pixel access
            self.pil_image = Image.open(self.image_path)
            self.image_array = np.array(self.pil_image)
            
            print(f"Image loaded successfully: {self.image_array.shape}")
            print(f"Image type: {self.image_array.dtype}")
            print(f"Number of channels: {self.image_array.shape[2] if len(self.image_array.shape) > 2 else 1}")
            
            return True
            
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def define_red_color_range(self):
        """
        Define the range of red colors to detect.
        """
        # Convert hex to RGB
        red_hex = "#B13C3A"
        red_rgb = tuple(int(red_hex[i:i+2], 16) for i in (1, 3, 5))
        
        # Define tolerance for red detection
        tolerance = 50
        
        # Create color ranges for different color spaces
        self.red_lower_hsv = np.array([0, 30, 30])  # Lower bound for red in HSV
        self.red_upper_hsv = np.array([20, 255, 255])  # Upper bound for red in HSV
        
        # Also try a second range for red (wrapping around 180)
        self.red_lower_hsv2 = np.array([160, 30, 30])
        self.red_upper_hsv2 = np.array([180, 255, 255])
        
        # RGB range for red
        self.red_lower_rgb = np.array([red_rgb[0] - tolerance, red_rgb[1] - tolerance, red_rgb[2] - tolerance])
        self.red_upper_rgb = np.array([red_rgb[0] + tolerance, red_rgb[1] + tolerance, red_rgb[2] + tolerance])
        
        print(f"Red color range (RGB): {self.red_lower_rgb} to {self.red_upper_rgb}")
        print(f"Red HSV range 1: {self.red_lower_hsv} to {self.red_upper_hsv}")
        print(f"Red HSV range 2: {self.red_lower_hsv2} to {self.red_upper_hsv2}")
    
    def find_red_pixels_entire_image(self):
        """
        Find red pixels in the entire cropped image.
        """
        if self.image_array is None:
            print("Image not loaded")
            return []
        
        # Handle different image formats (RGB vs RGBA)
        if len(self.image_array.shape) == 3:
            if self.image_array.shape[2] == 4:  # RGBA
                # Convert RGBA to RGB
                image_rgb = self.image_array[:, :, :3]
            else:  # RGB
                image_rgb = self.image_array
        else:
            print("Unsupported image format")
            return []
        
        # Convert to HSV for better color detection
        image_hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
        
        # Create mask for red pixels using both HSV ranges
        red_mask1 = cv2.inRange(image_hsv, self.red_lower_hsv, self.red_upper_hsv)
        red_mask2 = cv2.inRange(image_hsv, self.red_lower_hsv2, self.red_upper_hsv2)
        red_mask_hsv = cv2.bitwise_or(red_mask1, red_mask2)
        
        # Also try RGB-based detection
        red_mask_rgb = cv2.inRange(image_rgb, self.red_lower_rgb, self.red_upper_rgb)
        
        # Combine both masks
        combined_mask = cv2.bitwise_or(red_mask_hsv, red_mask_rgb)
        
        # Find coordinates of red pixels
        red_pixel_coords = np.where(combined_mask > 0)
        
        # Store pixel coordinates
        self.red_pixels = []
        for y, x in zip(red_pixel_coords[0], red_pixel_coords[1]):
            self.red_pixels.append((x, y))
        
        print(f"Found {len(self.red_pixels)} red pixels in the entire cropped image")
        return self.red_pixels
    
    def plot_red_pixels(self):
        """
        Plot the cropped image with red pixels marked and save the result.
        """
        if not self.red_pixels:
            print("No red pixels found to plot")
            return None
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
        
        # Original image
        ax1.imshow(self.image_rgb)
        ax1.set_title('Original Cropped Image')
        ax1.axis('off')
        
        # Image with red pixels marked
        ax2.imshow(self.image_rgb)
        
        # Mark red pixels with yellow circles for visibility
        for x, y in self.red_pixels:
            circle = plt.Circle((x, y), 2, color='yellow', fill=False, linewidth=1.5)
            ax2.add_patch(circle)
        
        ax2.set_title(f'Red Pixels Found ({len(self.red_pixels)} pixels)')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save the result
        output_path = 'cropped_image_red_pixels_analysis.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Analysis saved to: {output_path}")
        
        plt.show()
        
        return output_path
    
    def analyze_cropped_image(self):
        """
        Main method to perform complete analysis on the cropped image.
        """
        print("Starting cropped image analysis...")
        print(f"Target image: {self.image_path}")
        
        # Load image
        if not self.load_image():
            return False
        
        # Define red color range
        self.define_red_color_range()
        
        # Find red pixels in entire image
        self.find_red_pixels_entire_image()
        
        # Plot and save results
        output_path = self.plot_red_pixels()
        
        # Print summary
        print("\n" + "="*50)
        print("CROPPED IMAGE ANALYSIS SUMMARY")
        print("="*50)
        print(f"Image: {self.image_path}")
        print(f"Image dimensions: {self.image_array.shape}")
        print(f"Red pixels found: {len(self.red_pixels)}")
        
        if self.red_pixels:
            print("Red pixel coordinates (x, y):")
            for i, (x, y) in enumerate(self.red_pixels[:10]):  # Show first 10
                print(f"  {i+1}: ({x}, {y})")
            if len(self.red_pixels) > 10:
                print(f"  ... and {len(self.red_pixels) - 10} more")
        
        if output_path:
            print(f"Result saved to: {output_path}")
        print("="*50)
        
        return True

def main():
    """
    Main function to analyze the cropped image.
    """
    target_image = 'cropped_images/test.png'
    
    if os.path.exists(target_image):
        print(f"Analyzing cropped image: {target_image}")
        analyzer = CroppedImageAnalyzer(target_image)
        analyzer.analyze_cropped_image()
    else:
        print(f"Target image '{target_image}' not found.")
        print("Available files in cropped_images/:")
        if os.path.exists('cropped_images'):
            for f in os.listdir('cropped_images'):
                print(f"  - {f}")

if __name__ == "__main__":
    main()
