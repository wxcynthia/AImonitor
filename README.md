# PTSD Trigger Detection System

This system helps PTSD patients by monitoring screen content in real-time, detecting potential triggers based on user descriptions, and automatically recording the screen when triggers are detected.

[![View on GitHub](https://img.shields.io/badge/GitHub-View%20on%20GitHub-blue?style=for-the-badge&logo=github)](https://github.com/wxcynthia/AImonitor)
[![Visit Website](https://img.shields.io/badge/Website-Visit%20Website-green?style=for-the-badge&logo=github)](https://wxcynthia.github.io/AImonitor/)

## Overview

The system uses Google's Gemini AI to analyze screen content in real-time and identify potential PTSD triggers based on the user's specific description. When a trigger is detected, it automatically records the screen content.

### Key Features

- **Real-time Screen Monitoring**: Captures and analyzes a specific region of your screen.
- **AI-Powered Trigger Detection**: Uses Google Gemini to identify PTSD triggers based on your personal description.
- **Automatic Recording**: Starts recording when triggers are detected and stops after a configurable cooldown period.
- **Smart Glasses Integration**: Can be used to monitor content from connected Meta glasses through browser or app windows.

## Requirements

- Python 3.7+
- Google API Key with access to Gemini API
- Meta glasses (optional, for monitoring smart glasses feed)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/ptsd-detector.git
   cd ptsd-detector
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

### Monitoring a Screen Region

The main script monitors a specific region of your screen for PTSD triggers:

```
python mac_window_monitor.py --region x,y,width,height --display
```

Options:
- `--region`: Screen region to capture in format 'x,y,width,height'
- `--display`: Display the captured video while processing
- `--output`: Directory to save recorded videos

If you don't specify a region, the script will prompt you to enter one.

### Meta Glasses Integration

To monitor content from Meta glasses:

1. Connect your Meta glasses to your phone or computer
2. Open the Meta glasses viewing app or web interface
3. Use the `--region` parameter to specify the part of your screen where the Meta glasses feed is displayed
4. The system will analyze the glasses feed and detect triggers

Example:

```
python mac_window_monitor.py --region 100,100,800,600 --display
```

When prompted, enter a detailed description of your PTSD triggers.

## Output

When triggers are detected, the system:
1. Automatically starts recording the screen region
2. Continues recording for at least 5 seconds after the last trigger
3. Saves recordings to MP4, AVI, and JPG formats in the specified output directory

## Troubleshooting

- **"Error capturing screen area"**: Check if the specified region is valid and visible.
- **"Gemini API error"**: Verify your API key and internet connection.
- **"No frames to save"**: Make sure the recording duration is sufficient.

## Acknowledgments

Website design is based on the [Nerfies](https://github.com/nerfies/nerfies.github.io) project website.

## License

This project is licensed under the MIT License - see the LICENSE file for details.