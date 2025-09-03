# Color Detection Tools

This directory contains optimized color detection tools for analyzing images and detecting specific colors with high precision.

## 🎯 Features

- **Precise RGB-based color detection** - No more false positives from HSV conversion issues
- **Multiple color support** - Purple, Blue, Yellow, Orange
- **Optimized performance** - Efficient pixel analysis
- **Comprehensive reporting** - JSON reports with detailed statistics
- **Visual output** - Yellow-highlighted visualizations for manual checking
- **Organized results** - All outputs saved in `color_analysis_results/`

## 📁 Directory Structure

```
color_detection_tools/
├── README.md                    # This file
├── unified_color_detector.py    # Main detection engine
├── detect_purple.py            # Purple color detector
├── detect_blue.py              # Blue color detector
├── detect_yellow.py            # Yellow color detector
└── detect_orange.py            # Orange color detector

color_analysis_results/          # Output directory
├── purple_detection_*.png      # Purple visualizations
├── blue_detection_*.png        # Blue visualizations
├── yellow_detection_*.png      # Yellow visualizations
├── orange_detection_*.png      # Orange visualizations
├── purple_analysis_*.json      # Purple analysis reports
├── blue_analysis_*.json        # Blue analysis reports
├── yellow_analysis_*.json      # Yellow analysis reports
└── orange_analysis_*.json      # Orange analysis reports
```

## 🚀 Usage

### Individual Color Detection

```bash
# Detect purple colors
python color_detection_tools/detect_purple.py

# Detect blue colors
python color_detection_tools/detect_blue.py

# Detect yellow colors
python color_detection_tools/detect_yellow.py

# Detect orange colors
python color_detection_tools/detect_orange.py
```

### Comprehensive Analysis

```bash
# Analyze all colors at once
python color_detection_tools/unified_color_detector.py
```

## 🎨 Color Detection Rules

### Purple
- Blue component ≥ 70% of max component
- Green < Red and Green < Blue
- Color variation > 20
- Red > 20, Blue > 30

### Blue
- Blue > 120% of max(R, G)
- Color variation > 15
- Blue > 40

### Yellow
- Red > 100 and Green > 100
- Blue < 60% of min(R, G)
- Color variation > 20
- Red > 50 and Green > 50

### Orange
- Red > Green > Blue
- Red > 80
- Green: 30 < G < 80% of Red
- Blue < 50% of min(R, G)
- Color variation > 25

## 📊 Output Files

Each analysis generates:

1. **Visualization PNG** - Side-by-side comparison with yellow highlights
2. **JSON Report** - Detailed statistics and color information
3. **Console Output** - Real-time progress and summary

## 🔧 Customization

To modify color detection rules, edit the `color_rules` dictionary in `unified_color_detector.py`:

```python
self.color_rules = {
    'your_color': {
        'name': 'Your Color',
        'description': 'Description of your color',
        'rules': [
            lambda r, g, b: your_condition_1,
            lambda r, g, b: your_condition_2,
            # ... more rules
        ]
    }
}
```

## 📈 Performance

- **Optimized pixel analysis** - Efficient color counting
- **Memory efficient** - Processes large images without issues
- **Fast execution** - Typically completes in seconds
- **Progress indicators** - Real-time feedback during analysis

## 🎯 Accuracy

- **No false positives** - Precise RGB-based rules eliminate misidentification
- **Validated results** - Each detected color passes multiple validation criteria
- **Manual verification** - Yellow highlights allow easy visual confirmation

## 📝 Example Output

```
🎨 ANALYZING PURPLE COLORS
============================================================
🎯 Detecting Purple colors...
📝 Colors with significant blue, present red, and low green
✅ Found 3 purple color(s)
📊 Total purple pixels: 1,432 (0.18% of image)

🔝 Top purple colors:
   1: RGB(142,  39, 162) -   1,330 pixels ( 0.17%)
   2: RGB(107,  33, 121) -      54 pixels ( 0.01%)
   3: RGB(197, 137, 207) -      48 pixels ( 0.01%)
```

## 🛠️ Requirements

- Python 3.6+
- numpy
- matplotlib
- PIL (Pillow)

## 📞 Support

For issues or questions about the color detection tools, check the console output for detailed error messages and analysis results.
