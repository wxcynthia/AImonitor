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