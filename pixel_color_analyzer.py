import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

class PixelColorAnalyzer:
    def __init__(self, image_path):
        """
        Initialize the pixel color analyzer with an image path.
        
        Args:
            image_path (str): Path to the image file
        """
        self.image_path = image_path
        self.image = None
        self.image_array = None
        self.red_pixels = []
        
    def load_image(self):
        """Load the image using both OpenCV and PIL for different operations."""
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
            return True
            
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def define_red_color_range(self):
        """
        Define the range of red colors to detect.
        Based on the image description, red appears to be around #EF5350.
        """
        # Convert hex to RGB
        red_hex = "#EF5350"
        red_rgb = tuple(int(red_hex[i:i+2], 16) for i in (1, 3, 5))
        
        # Define tolerance for red detection - more flexible
        tolerance = 50
        
        # Create color ranges for different color spaces - more inclusive
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
    
    def detect_stm_area(self):
        """
        Detect the STM indicator area (white line oscillator at the bottom).
        This is the area with the white line and red filled area below it.
        """
        height, width = self.image_array.shape[:2]
        
        # Based on the image description, STM is at the bottom
        # The white line is in the bottom section with red filled area below
        bottom_start = int(height * 0.85)  # Start from 85% of image height
        bottom_end = height  # To the bottom
        
        # Focus on the rightmost portion for analysis
        right_start = int(width * 0.7)  # Start from 70% of image width
        right_end = width  # To the right edge
        
        self.stm_area = {
            'y_start': bottom_start,
            'y_end': bottom_end,
            'x_start': right_start,
            'x_end': right_end
        }
        
        print(f"STM area defined: x({right_start}-{right_end}), y({bottom_start}-{bottom_end})")
        return self.stm_area
    
    def find_red_pixels_in_stm(self):
        """
        Find red pixels in the STM indicator area.
        """
        if self.stm_area is None:
            self.detect_stm_area()
        
        # Extract the STM area
        stm_region = self.image_array[
            self.stm_area['y_start']:self.stm_area['y_end'],
            self.stm_area['x_start']:self.stm_area['x_end']
        ]
        
        # Convert to HSV for better color detection
        stm_hsv = cv2.cvtColor(stm_region, cv2.COLOR_RGB2HSV)
        
        # Create mask for red pixels using both HSV ranges
        red_mask1 = cv2.inRange(stm_hsv, self.red_lower_hsv, self.red_upper_hsv)
        red_mask2 = cv2.inRange(stm_hsv, self.red_lower_hsv2, self.red_upper_hsv2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        
        # Also try RGB-based detection as backup
        stm_rgb = stm_region
        # Ensure the RGB bounds are the right shape for the image
        if stm_rgb.ndim == 3:
            red_mask_rgb = cv2.inRange(stm_rgb, self.red_lower_rgb, self.red_upper_rgb)
        else:
            red_mask_rgb = np.zeros_like(red_mask)
        
        # Combine both masks
        combined_mask = cv2.bitwise_or(red_mask, red_mask_rgb)
        
        # Find coordinates of red pixels
        red_pixel_coords = np.where(combined_mask > 0)
        
        # Convert relative coordinates to absolute image coordinates
        self.red_pixels = []
        for y, x in zip(red_pixel_coords[0], red_pixel_coords[1]):
            abs_x = x + self.stm_area['x_start']
            abs_y = y + self.stm_area['y_start']
            self.red_pixels.append((abs_x, abs_y))
        
        print(f"Found {len(self.red_pixels)} red pixels in STM area")
        
        # If no red pixels found, let's also check the entire bottom area
        if len(self.red_pixels) == 0:
            print("No red pixels found in STM area, checking entire bottom section...")
            self.find_red_pixels_in_bottom_section()
        
        return self.red_pixels
    
    def find_red_pixels_in_bottom_section(self):
        """
        Find red pixels in the entire bottom section of the image.
        """
        height, width = self.image_array.shape[:2]
        
        # Check the entire bottom 20% of the image
        bottom_start = int(height * 0.8)
        bottom_end = height
        
        bottom_region = self.image_array[bottom_start:bottom_end, :]
        bottom_hsv = cv2.cvtColor(bottom_region, cv2.COLOR_RGB2HSV)
        
        # Create mask for red pixels
        red_mask1 = cv2.inRange(bottom_hsv, self.red_lower_hsv, self.red_upper_hsv)
        red_mask2 = cv2.inRange(bottom_hsv, self.red_lower_hsv2, self.red_upper_hsv2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        
        # Find coordinates of red pixels
        red_pixel_coords = np.where(red_mask > 0)
        
        # Convert relative coordinates to absolute image coordinates
        for y, x in zip(red_pixel_coords[0], red_pixel_coords[1]):
            abs_x = x
            abs_y = y + bottom_start
            self.red_pixels.append((abs_x, abs_y))
        
        print(f"Found {len(self.red_pixels)} red pixels in entire bottom section")
    
    def plot_red_pixels(self):
        """
        Plot the image with red pixels marked and save the result.
        """
        if not self.red_pixels:
            print("No red pixels found to plot")
            return
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        
        # Original image
        ax1.imshow(self.image_rgb)
        ax1.set_title('Original Image')
        ax1.axis('off')
        
        # Image with red pixels marked
        ax2.imshow(self.image_rgb)
        
        # Mark red pixels with yellow circles for visibility
        for x, y in self.red_pixels:
            circle = plt.Circle((x, y), 3, color='yellow', fill=False, linewidth=2)
            ax2.add_patch(circle)
        
        # Draw rectangle around STM area
        stm_rect = plt.Rectangle(
            (self.stm_area['x_start'], self.stm_area['y_start']),
            self.stm_area['x_end'] - self.stm_area['x_start'],
            self.stm_area['y_end'] - self.stm_area['y_start'],
            linewidth=2, edgecolor='cyan', facecolor='none'
        )
        ax2.add_patch(stm_rect)
        
        ax2.set_title(f'Red Pixels Found in STM Area ({len(self.red_pixels)} pixels)')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save the result
        output_path = 'stm_red_pixels_analysis.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Analysis saved to: {output_path}")
        
        plt.show()
        
        return output_path
    
    def analyze_pixel_colors(self):
        """
        Main method to perform complete pixel color analysis.
        """
        print("Starting pixel color analysis...")
        
        # Load image
        if not self.load_image():
            return False
        
        # Define red color range
        self.define_red_color_range()
        
        # Detect STM area
        self.detect_stm_area()
        
        # Find red pixels
        self.find_red_pixels_in_stm()
        
        # Plot and save results
        output_path = self.plot_red_pixels()
        
        # Print summary
        print("\n" + "="*50)
        print("ANALYSIS SUMMARY")
        print("="*50)
        print(f"Image: {self.image_path}")
        print(f"Image dimensions: {self.image_array.shape}")
        print(f"STM area: x({self.stm_area['x_start']}-{self.stm_area['x_end']}), y({self.stm_area['y_start']}-{self.stm_area['y_end']})")
        print(f"Red pixels found: {len(self.red_pixels)}")
        
        if self.red_pixels:
            print("Red pixel coordinates (x, y):")
            for i, (x, y) in enumerate(self.red_pixels[:10]):  # Show first 10
                print(f"  {i+1}: ({x}, {y})")
            if len(self.red_pixels) > 10:
                print(f"  ... and {len(self.red_pixels) - 10} more")
        
        print(f"Result saved to: {output_path}")
        print("="*50)
        
        return True

def main():
    """
    Main function to run the pixel color analyzer.
    """
    # List available images
    image_files = [f for f in os.listdir('.') if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    cropped_files = [f for f in os.listdir('cropped_images') if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    print("Available image files:")
    for i, img in enumerate(image_files):
        print(f"{i+1}. {img}")
    
    print("\nAvailable cropped image files:")
    for i, img in enumerate(cropped_files):
        print(f"{i+1}. cropped_images/{img}")
    
    # Try to analyze both the main test image and cropped images
    target_images = ['test.png', 'cropped_images/test.png']
    
    for target_image in target_images:
        if os.path.exists(target_image):
            print(f"\n{'='*60}")
            print(f"Analyzing image: {target_image}")
            print(f"{'='*60}")
            analyzer = PixelColorAnalyzer(target_image)
            analyzer.analyze_pixel_colors()
        else:
            print(f"Target image '{target_image}' not found.")

if __name__ == "__main__":
    main()
