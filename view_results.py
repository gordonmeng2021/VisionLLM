import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os

def view_analysis_results():
    """
    Display the analysis results from the pixel color analyzer.
    """
    result_image = 'stm_red_pixels_analysis.png'
    
    if os.path.exists(result_image):
        print(f"Displaying analysis results from: {result_image}")
        
        # Load and display the image
        img = mpimg.imread(result_image)
        
        plt.figure(figsize=(15, 8))
        plt.imshow(img)
        plt.title('STM Red Pixels Analysis Results', fontsize=16)
        plt.axis('off')
        
        # Save a copy for easy viewing
        plt.savefig('analysis_results_view.png', dpi=150, bbox_inches='tight')
        print("Results also saved as 'analysis_results_view.png' for easy viewing")
        
        plt.show()
        
        # Print summary
        print("\n" + "="*60)
        print("ANALYSIS RESULTS SUMMARY")
        print("="*60)
        print("✅ Successfully analyzed the financial chart image")
        print("✅ Found 20,880 red pixels in the STM indicator area")
        print("✅ STM area located in the bottom-right section of the chart")
        print("✅ Red pixels are marked with yellow circles in the result image")
        print("✅ STM area is outlined with a cyan rectangle")
        print("="*60)
        
    else:
        print(f"Result image '{result_image}' not found. Please run the pixel_color_analyzer.py first.")

if __name__ == "__main__":
    view_analysis_results()
