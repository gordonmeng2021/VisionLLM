import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os
import json
from datetime import datetime

class UnifiedColorDetector:
    def __init__(self, image_path, output_dir="color_analysis_results"):
        """
        Initialize the unified color detector.
        
        Args:
            image_path (str): Path to the image file
            output_dir (str): Directory to save results
        """
        self.image_path = image_path
        self.output_dir = output_dir
        self.image_array = None
        self.rgb_image = None
        self.unique_colors = {}
        self.sorted_colors = []
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Define color detection rules for each color
        self.color_rules = {
            'purple': {
                'name': 'Purple',
                'description': 'Colors with significant blue, present red, and low green',
                'rules': [
                    lambda r, g, b: b >= max(r, g) * 0.7,  # Blue significant
                    lambda r, g, b: g < r and g < b,       # Green lower than R and B
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 20,  # Color variation
                    lambda r, g, b: r > 20,                # Red present
                    lambda r, g, b: b > 30,                # Blue present
                ]
            },
            'blue': {
                'name': 'Blue',
                'description': 'Colors with dominant blue component',
                'rules': [
                    lambda r, g, b: b > max(r, g) * 1.2,   # Blue significantly dominant
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 15,  # Color variation
                    lambda r, g, b: b > 40,                # Blue present
                ]
            },
            'yellow': {
                'name': 'Yellow',
                'description': 'Colors with similar high red and green values, controlled blue',
                'rules': [
                    lambda r, g, b: r > 100 and g > 100,   # High red and green (lowered threshold)
                    lambda r, g, b: abs(int(r) - int(g)) < 80,       # Red and green should be similar (more relaxed)
                    lambda r, g, b: b < min(r, g) * 0.65,  # Blue less than 65% of min(R,G) (more relaxed)
                    lambda r, g, b: b < 150,               # Blue absolute limit (increased)
                    lambda r, g, b: min(r, g) > max(r, g) * 0.6,   # R and G should be reasonably close (more relaxed)
                    lambda r, g, b: int(r) + int(g) > 2 * int(b) + 50,    # Yellow color space rule (more relaxed)
                    lambda r, g, b: r > g * 0.7 and g > r * 0.7,   # Neither R nor G dominates too much (more relaxed)
                    lambda r, g, b: r > 50 and g > 50,     # Minimum brightness to avoid dark colors
                ]
            },
            'orange': {
                'name': 'Orange',
                'description': 'Colors with high red, medium green, low blue',
                'rules': [
                    lambda r, g, b: r > g and g > b,       # R > G > B
                    lambda r, g, b: r > 80,                # High red
                    lambda r, g, b: g > 30 and g < r * 0.8,  # Medium green
                    lambda r, g, b: b < min(r, g) * 0.5,   # Low blue
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 25,  # Color variation
                ]
            },
            'red': {
                'name': 'Red',
                'description': 'Colors with dominant red component, excluding orange',
                'rules': [
                    lambda r, g, b: r > max(g, b) * 1.2,   # Red dominant but not as strict
                    lambda r, g, b: r > 100,               # High red value
                    lambda r, g, b: g < r * 0.6,           # Green much lower than red (stricter to avoid orange)
                    lambda r, g, b: b < r * 0.6,           # Blue much lower than red
                    lambda r, g, b: r - g > 50,            # Red significantly higher than green (avoid orange)
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 40,  # Good color variation
                ]
            },
            'green': {
                'name': 'Green',
                'description': 'Colors with significant green component, including teal-green',
                'rules': [
                    lambda r, g, b: g > max(r, b),         # Green is highest component
                    lambda r, g, b: g > 50,                # Minimum green value
                    lambda r, g, b: g - max(r, b) > 10,    # Green noticeably higher (more lenient)
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 15,  # Some color variation
                    lambda r, g, b: g > 80 or (g > r * 1.5 and g > b * 0.8),  # Either bright green OR green dominant over red with reasonable blue
                ]
            },
            'gray': {
                'name': 'Gray',
                'description': 'Colors with similar RGB values (neutral colors), excluding black and white',
                'rules': [
                    lambda r, g, b: abs(int(r) - int(g)) <= 15,  # Red and green are similar
                    lambda r, g, b: abs(int(g) - int(b)) <= 15,  # Green and blue are similar
                    lambda r, g, b: abs(int(r) - int(b)) <= 15,  # Red and blue are similar
                    lambda r, g, b: max(r, g, b) - min(r, g, b) <= 20,  # Low color variation
                    lambda r, g, b: min(r, g, b) >= 50,    # Exclude black colors (raised from 10 to 50)
                    lambda r, g, b: max(r, g, b) <= 200,   # Not pure white (to avoid very bright whites)
                    lambda r, g, b: max(r, g, b) >= 70,    # Ensure it's bright enough to be considered gray
                ]
            },
            'fuchsia': {
                'name': 'Fuchsia',
                'description': 'Bright magenta/pink colors with high red and blue, low green',
                'rules': [
                    lambda r, g, b: r > 150 and b > 150,   # High red and blue
                    lambda r, g, b: g < min(r, b) * 0.7,   # Green much lower than red and blue
                    lambda r, g, b: abs(int(r) - int(b)) < 80,  # Red and blue should be reasonably similar
                    lambda r, g, b: max(r, b) > g * 1.5,   # Either red or blue dominates over green
                    lambda r, g, b: max(r, g, b) - min(r, g, b) > 40,  # Good color variation
                    lambda r, g, b: int(r) + int(b) > 2 * int(g) + 100,   # Fuchsia color space rule
                ]
            },
            'aqua': {
                'name': 'Aqua',
                'description': 'Cyan/aqua colors with high blue and green, low red - distinct from pure blue',
                'rules': [
                    lambda r, g, b: b > 100 and g > 100,   # High blue and green components
                    lambda r, g, b: r < min(b, g) * 0.6,   # Red significantly lower than blue and green
                    lambda r, g, b: abs(int(b) - int(g)) < 100,  # Blue and green should be reasonably similar
                    lambda r, g, b: min(b, g) > max(b, g) * 0.7,  # Both blue and green should be substantial
                    lambda r, g, b: g > 80,                # Ensure sufficient green to distinguish from pure blue
                    lambda r, g, b: b > g * 0.8,           # Blue should be at least 80% of green value
                    lambda r, g, b: int(b) + int(g) > 2 * int(r) + 80,   # Aqua color space rule
                    lambda r, g, b: max(b, g, r) - min(b, g, r) > 30,  # Good color variation
                ]
            }
        }
    
    def load_image(self):
        """Load and prepare the image for analysis."""
        try:
            pil_image = Image.open(self.image_path)
            self.image_array = np.array(pil_image)
            print(f"✅ Image loaded: {self.image_array.shape}")
            
            # Convert to RGB
            if len(self.image_array.shape) == 3:
                if self.image_array.shape[2] == 4:  # RGBA
                    self.rgb_image = self.image_array[:, :, :3]
                else:  # RGB
                    self.rgb_image = self.image_array
            else:
                print("❌ Unsupported image format")
                return False
            
            print(f"✅ RGB image shape: {self.rgb_image.shape}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading image: {e}")
            return False
    
    def analyze_unique_colors(self):
        """Analyze and count unique colors in the image."""
        print("🔍 Analyzing unique colors...")
        
        # Reshape to get all pixels
        pixels = self.rgb_image.reshape(-1, 3)
        print(f"📊 Total pixels: {len(pixels):,}")
        
        # Count unique colors efficiently
        self.unique_colors = {}
        for pixel in pixels:
            pixel_tuple = tuple(pixel)
            self.unique_colors[pixel_tuple] = self.unique_colors.get(pixel_tuple, 0) + 1
        
        # Sort by frequency
        self.sorted_colors = sorted(self.unique_colors.items(), key=lambda x: x[1], reverse=True)
        
        print(f"🎨 Unique colors found: {len(self.unique_colors):,}")
        return self.sorted_colors
    
    def detect_color(self, color_name):
        """
        Detect pixels of a specific color using the defined rules.
        
        Args:
            color_name (str): Name of the color to detect ('purple', 'blue', 'yellow', 'orange')
        
        Returns:
            list: List of (RGB, count) tuples for detected colors
        """
        if color_name not in self.color_rules:
            print(f"❌ Unknown color: {color_name}")
            print(f"Available colors: {list(self.color_rules.keys())}")
            return []
        
        color_info = self.color_rules[color_name]
        rules = color_info['rules']
        
        print(f"\n🎯 Detecting {color_info['name']} colors...")
        print(f"📝 {color_info['description']}")
        
        detected_colors = []
        total_pixels = sum(count for _, count in self.unique_colors.items())
        
        for (r, g, b), count in self.sorted_colors:
            # Apply all rules
            if all(rule(r, g, b) for rule in rules):
                detected_colors.append(((r, g, b), count))
        
        if detected_colors:
            total_detected = sum(count for _, count in detected_colors)
            percentage = (total_detected / total_pixels) * 100
            
            print(f"✅ Found {len(detected_colors)} {color_info['name'].lower()} color(s)")
            print(f"📊 Total {color_info['name'].lower()} pixels: {total_detected:,} ({percentage:.2f}% of image)")
            
            # Show top colors
            print(f"\n🔝 Top {color_info['name'].lower()} colors:")
            for i, ((r, g, b), count) in enumerate(detected_colors[:10]):
                color_percentage = (count / total_pixels) * 100
                print(f"  {i+1:2d}: RGB({r:3d}, {g:3d}, {b:3d}) - {count:6,} pixels ({color_percentage:5.2f}%)")
        else:
            print(f"❌ No {color_info['name'].lower()} colors found")
        
        return detected_colors
    
    def create_visualization(self, color_name, detected_colors):
        """
        Create visualization for detected colors.
        
        Args:
            color_name (str): Name of the detected color
            detected_colors (list): List of detected color tuples
        """
        if not detected_colors:
            print(f"❌ No {color_name} colors to visualize")
            return None
        
        # Create mask for detected colors
        color_mask = np.zeros(self.rgb_image.shape[:2], dtype=bool)
        detected_rgb_values = [rgb for (rgb, count) in detected_colors]
        
        # Create mask efficiently
        for y in range(self.rgb_image.shape[0]):
            for x in range(self.rgb_image.shape[1]):
                pixel_rgb = tuple(self.rgb_image[y, x])
                if pixel_rgb in detected_rgb_values:
                    color_mask[y, x] = True
        
        # Create visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Original image
        ax1.imshow(self.rgb_image)
        ax1.set_title('Original Image', fontsize=14, fontweight='bold')
        ax1.axis('off')
        
        # Highlight detected colors
        overlay_image = self.rgb_image.copy()
        color_pixels = np.where(color_mask)
        overlay_image[color_pixels] = [255, 255, 0]  # Bright yellow highlight
        
        total_detected = sum(count for _, count in detected_colors)
        ax2.imshow(overlay_image)
        ax2.set_title(f'{color_name.title()} Colors Detected\n({total_detected:,} pixels)', 
                     fontsize=14, fontweight='bold')
        ax2.axis('off')
        
        plt.tight_layout()
        
        # Save result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f'{color_name}_detection_{timestamp}.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"💾 Visualization saved to: {output_path}")
        
        plt.show()
        
        return output_path
    
    def save_analysis_report(self, color_name, detected_colors, output_path):
        """
        Save detailed analysis report to JSON file.
        
        Args:
            color_name (str): Name of the detected color
            detected_colors (list): List of detected color tuples
            output_path (str): Path to the visualization
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.output_dir, f'{color_name}_analysis_{timestamp}.json')
        
        total_pixels = sum(count for _, count in self.unique_colors.items())
        total_detected = sum(count for _, count in detected_colors)
        
        report = {
            'analysis_info': {
                'timestamp': timestamp,
                'image_path': self.image_path,
                'image_dimensions': [int(d) for d in self.image_array.shape],
                'total_pixels': int(total_pixels),
                'unique_colors': int(len(self.unique_colors))
            },
            'color_detection': {
                'color_name': color_name,
                'color_info': {
                    'name': self.color_rules[color_name]['name'],
                    'description': self.color_rules[color_name]['description']
                },
                'detected_colors_count': int(len(detected_colors)),
                'total_detected_pixels': int(total_detected),
                'percentage_of_image': float((total_detected / total_pixels) * 100)
            },
            'detected_colors': [
                {
                    'rgb': [int(c) for c in rgb],
                    'pixel_count': int(count),
                    'percentage': float((count / total_pixels) * 100)
                }
                for rgb, count in detected_colors
            ],
            'output_files': {
                'visualization': output_path,
                'report': report_path
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Analysis report saved to: {report_path}")
        return report_path
    
    def analyze_color(self, color_name):
        """
        Complete analysis for a specific color.
        
        Args:
            color_name (str): Name of the color to analyze
        
        Returns:
            dict: Analysis results
        """
        print(f"\n{'='*60}")
        print(f"🎨 ANALYZING {color_name.upper()} COLORS")
        print(f"{'='*60}")
        
        # Detect colors
        detected_colors = self.detect_color(color_name)
        
        if detected_colors:
            # Create visualization
            output_path = self.create_visualization(color_name, detected_colors)
            
            # Save report
            report_path = self.save_analysis_report(color_name, detected_colors, output_path)
            
            return {
                'color_name': color_name,
                'detected_colors': detected_colors,
                'visualization_path': output_path,
                'report_path': report_path,
                'success': True
            }
        else:
            return {
                'color_name': color_name,
                'detected_colors': [],
                'visualization_path': None,
                'report_path': None,
                'success': False
            }
    
    def analyze_all_colors(self):
        """
        Analyze all supported colors in the image.
        
        Returns:
            dict: Results for all colors
        """
        print(f"\n{'='*60}")
        print("🌈 COMPREHENSIVE COLOR ANALYSIS")
        print(f"{'='*60}")
        
        # Load image and analyze unique colors
        if not self.load_image():
            return None
        
        self.analyze_unique_colors()
        
        # Analyze each color
        results = {}
        for color_name in self.color_rules.keys():
            results[color_name] = self.analyze_color(color_name)
        
        # Print summary
        print(f"\n{'='*60}")
        print("📊 ANALYSIS SUMMARY")
        print(f"{'='*60}")
        
        for color_name, result in results.items():
            if result['success']:
                total_pixels = sum(count for _, count in result['detected_colors'])
                print(f"✅ {color_name.title()}: {total_pixels:,} pixels detected")
            else:
                print(f"❌ {color_name.title()}: No pixels detected")
        
        return results

def main():
    """
    Main function to run color analysis.
    """
    target_image = 'cropped_images/test.png'
    
    if not os.path.exists(target_image):
        print(f"❌ Target image '{target_image}' not found.")
        return
    
    # Create detector
    detector = UnifiedColorDetector(target_image)
    
    # Analyze all colors
    results = detector.analyze_all_colors()
    
    if results:
        print(f"\n🎉 Analysis complete! Check the 'color_analysis_results' directory for detailed reports.")

if __name__ == "__main__":
    main()
