import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os
from collections import Counter

class HexColorExtractor:
    def __init__(self, image_path):
        """
        Initialize the hex color extractor.
        
        Args:
            image_path (str): Path to the image file
        """
        self.image_path = image_path
        self.image_array = None
        self.unique_colors = []
        self.color_counts = {}
        
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
    
    def extract_hex_colors(self):
        """
        Extract all unique hex color codes from the image.
        """
        if self.image_array is None:
            print("Image not loaded")
            return []
        
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
        
        # Reshape the image to a list of pixels
        pixels = image_rgb.reshape(-1, 3)
        
        # Convert to hex colors
        hex_colors = []
        for pixel in pixels:
            r, g, b = pixel
            hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
            hex_colors.append(hex_color)
        
        # Count occurrences of each color
        self.color_counts = Counter(hex_colors)
        
        # Get unique colors sorted by frequency
        self.unique_colors = sorted(self.color_counts.items(), key=lambda x: x[1], reverse=True)
        
        print(f"Found {len(self.unique_colors)} unique colors in the image")
        return self.unique_colors
    
    def display_hex_colors(self, top_n=20):
        """
        Display the hex color codes found in the image.
        
        Args:
            top_n (int): Number of top colors to display
        """
        if not self.unique_colors:
            print("No colors extracted yet. Run extract_hex_colors() first.")
            return
        
        print(f"\n{'='*60}")
        print(f"HEX COLOR CODES FOUND IN IMAGE")
        print(f"{'='*60}")
        print(f"Total unique colors: {len(self.unique_colors)}")
        print(f"Showing top {min(top_n, len(self.unique_colors))} most frequent colors:")
        print(f"{'='*60}")
        
        for i, (hex_color, count) in enumerate(self.unique_colors[:top_n]):
            # Convert hex to RGB for display
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
            percentage = (count / sum(self.color_counts.values())) * 100
            
            print(f"{i+1:2d}. {hex_color} | RGB({rgb[0]:3d}, {rgb[1]:3d}, {rgb[2]:3d}) | Count: {count:6d} ({percentage:5.2f}%)")
        
        if len(self.unique_colors) > top_n:
            print(f"... and {len(self.unique_colors) - top_n} more colors")
        
        print(f"{'='*60}")
    
    def find_red_colors(self):
        """
        Find colors that are predominantly red.
        """
        if not self.unique_colors:
            print("No colors extracted yet. Run extract_hex_colors() first.")
            return []
        
        red_colors = []
        
        for hex_color, count in self.unique_colors:
            # Convert hex to RGB
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
            r, g, b = rgb
            
            # Check if this is a red color (red component is significantly higher than green and blue)
            if r > g and r > b and r > 100:  # Red is dominant and bright enough
                red_colors.append((hex_color, rgb, count))
        
        print(f"\n{'='*60}")
        print(f"RED COLORS FOUND")
        print(f"{'='*60}")
        
        if red_colors:
            for i, (hex_color, rgb, count) in enumerate(red_colors):
                percentage = (count / sum(self.color_counts.values())) * 100
                print(f"{i+1:2d}. {hex_color} | RGB({rgb[0]:3d}, {rgb[1]:3d}, {rgb[2]:3d}) | Count: {count:6d} ({percentage:5.2f}%)")
        else:
            print("No predominantly red colors found.")
        
        print(f"{'='*60}")
        return red_colors
    
    def create_color_palette(self, top_n=20):
        """
        Create a visual color palette of the most frequent colors.
        """
        if not self.unique_colors:
            print("No colors extracted yet. Run extract_hex_colors() first.")
            return
        
        # Take top N colors
        top_colors = self.unique_colors[:top_n]
        
        # Create a figure to display the color palette
        fig, ax = plt.subplots(figsize=(15, 8))
        
        # Create color bars
        bar_height = 1
        y_positions = np.arange(len(top_colors))
        
        for i, (hex_color, count) in enumerate(top_colors):
            # Convert hex to RGB for matplotlib
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
            normalized_rgb = (rgb[0]/255, rgb[1]/255, rgb[2]/255)
            
            # Create color bar
            ax.barh(i, count, height=bar_height, color=normalized_rgb, edgecolor='black', linewidth=0.5)
            
            # Add text labels
            percentage = (count / sum(self.color_counts.values())) * 100
            ax.text(count + max([c[1] for c in top_colors]) * 0.01, i, 
                   f"{hex_color} ({percentage:.1f}%)", 
                   va='center', fontsize=8)
        
        ax.set_yticks(y_positions)
        ax.set_yticklabels([f"{i+1}" for i in range(len(top_colors))])
        ax.set_xlabel('Pixel Count')
        ax.set_ylabel('Color Rank')
        ax.set_title(f'Top {len(top_colors)} Colors in {os.path.basename(self.image_path)}')
        
        plt.tight_layout()
        
        # Save the palette
        output_path = 'color_palette.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Color palette saved to: {output_path}")
        
        plt.show()
        return output_path
    
    def analyze_image_colors(self):
        """
        Main method to perform complete color analysis.
        """
        print("Starting hex color extraction...")
        print(f"Target image: {self.image_path}")
        
        # Load image
        if not self.load_image():
            return False
        
        # Extract hex colors
        self.extract_hex_colors()
        
        # Display results
        self.display_hex_colors(top_n=30)
        
        # Find red colors specifically
        red_colors = self.find_red_colors()
        
        # Create visual palette
        self.create_color_palette(top_n=20)
        
        return True

def main():
    """
    Main function to extract hex colors from the cropped image.
    """
    target_image = 'cropped_images/vertical_rectangle.png'
    
    if os.path.exists(target_image):
        print(f"Extracting hex colors from: {target_image}")
        extractor = HexColorExtractor(target_image)
        extractor.analyze_image_colors()
    else:
        print(f"Target image '{target_image}' not found.")
        print("Available files in cropped_images/:")
        if os.path.exists('cropped_images'):
            for f in os.listdir('cropped_images'):
                print(f"  - {f}")

if __name__ == "__main__":
    main()
