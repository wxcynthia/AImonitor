<<<<<<< HEAD
# The Neuro-AI Revolution: Closed-Loop Systems, LLM Agents, and the Future of Neural Science

This repository contains the project website for our work on integrating neural implants, wearable sensors, and LLM agents to create a closed-loop intervention system for PTSD and other neurological conditions.

## Abstract

We present a comprehensive system that integrates responsive neural implants with multimodal large language models (LLMs) for real-time monitoring and intervention in patients with PTSD. This closed-loop approach combines invasive neural sensing/stimulation with wearable context sensing and AI interpretation to address PTSD on multiple levels – neurobiological, physiological, and psychological. The system can detect triggers and provide personalized interventions precisely when needed, improving upon current responsive neurostimulation techniques that rely primarily on neural signals alone.

## Key Features

- Integration of neural implants with wearable sensors
- Real-time analysis using multimodal LLMs
- Personalized intervention for PTSD triggers
- Extensible to other neurological and psychiatric conditions

## Citation

# Neuro-AI Revolution Project Website

This repository contains the code for the project website for "The Neuro-AI Revolution: Closed-Loop Systems, LLM Agents, and the Future of Neural Science" paper.

The website design is based on the [Nerfies](https://github.com/nerfies/nerfies.github.io) project website.

## Setup Instructions

### Prerequisites
- Git
- A text editor
- Basic knowledge of HTML, CSS, and JavaScript

### Installation

1. Clone this repository:
```
git clone https://github.com/YourUsername/YourRepoName.git
cd YourRepoName
```

2. Directory Structure:
```
├── index.html
├── README.md
├── static
│   ├── css
│   │   ├── bulma.min.css
│   │   ├── bulma-carousel.min.css
│   │   ├── bulma-slider.min.css
│   │   ├── fontawesome.all.min.css
│   │   └── index.css
│   ├── images
│   │   ├── figure1.png
│   │   ├── figure2.png
│   │   └── case_study.png
│   ├── js
│   │   ├── bulma-carousel.min.js
│   │   ├── bulma-slider.min.js
│   │   ├── fontawesome.all.min.js
│   │   └── index.js
│   ├── pdfs
│   │   └── paper.pdf
│   └── videos
│       └── teaser.mp4
```

3. Adding Your Content:
   - Replace placeholder images in the `static/images/` directory with your own figures
   - Add your video to the `static/videos/` directory (name it `teaser.mp4` or update the HTML to reflect your filename)
   - Add your paper PDF to the `static/pdfs/` directory
   - Update links, titles, and author information in `index.html`

4. Required External Libraries:
   - Bulma CSS framework
   - Font Awesome icons
   - Academic Icons
   - jQuery
   - Bulma carousel and slider extensions

   All these are already linked in the HTML file via CDN or included in the repository.

5. Testing locally:
   - You can view the website locally by opening the `index.html` file in your browser
   - For a better experience, use a local server (like Python's `http.server`):
     ```
     python -m http.server
     ```
     Then visit `http://localhost:8000` in your browser.

6. Deploying to GitHub Pages:
   - Push your changes to GitHub
   - In your repository settings, enable GitHub Pages for the main branch
   - Your website will be available at `https://YourUsername.github.io/YourRepoName/`

## Customization

### Adding/Changing Content

1. **To add more figures/images:**
   - Add your image files to the `static/images/` directory
   - Create a new section in `index.html` following the existing section patterns
   - Use the Bulma CSS classes for layout

2. **To modify the video:**
   - Replace the `teaser.mp4` file in the `static/videos/` directory
   - If your video has a different aspect ratio, you may need to adjust the CSS

3. **To update author information, abstract, etc.:**
   - Edit the corresponding sections in `index.html`

### Styling

- The main styling is in `static/css/index.css`
- The site uses the Bulma CSS framework, so you can use Bulma classes for layout
- Font styles, colors, and spacing can be adjusted in the CSS file

## License

This template is based on the [Nerfies](https://github.com/nerfies/nerfies.github.io) project website, which is released under the MIT License.

## Issues and Contributions

If you encounter any issues or would like to contribute to this project, please open an issue or pull request on GitHub.

## Related Projects

- [AI-Centered Language](https://wxcynthia.github.io/AIlanguage/)
- [Video Analysis Public](https://huggingface.co/spaces/wxcyn/Video-Analysis-Public)

## Website Template

This website is based on the [Nerfies](https://github.com/nerfies/nerfies.github.io) project page.
=======
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
>>>>>>> 5319e95c1c0f6afd2e14542f6fca79259a9e6324
