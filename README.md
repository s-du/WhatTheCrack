<p align="center">
    <a href="https://ibb.co/tpP370H"><img src="https://i.ibb.co/Tv27JMC/Whatthecrack3.png" alt="Whatthecrack2" border="0" style="width: 100%;"></a>
</p>

## Overview
WhatTheCrack is a intuitive tool designed for detecting cracks in construction materials. This application leverages the capabilities of YOLO V8 and SAHI, providing users with an intuitive graphical interface for straightforward measurements&#8203;``【oaicite:3】``&#8203;.

**The project is still in pre-release, so do not hesitate to send your recommendations or the bugs you encountered!**

## Features
The app offers the following key features:
- User-friendly GUI for simple measurements.
- Simple 'painting' solution to quickly annotate cracks
- Advanced crack segmentation on construction materials.
  - Integration with YOLO V8 and SAHI for cutting-edge image processing.
  - Segmentation results can be completed with manual painting
- Graph analysis for crack structure determination (NetworkX)
  - Identification of end points and junctions
  - Measurement of the exact length of all cracks, based on the computed structure   

## Files and Structure
- `resources/`: Contains essential resources for the application.
- `sahi/`: Modified SAHI module for image segmentation and analysis.
- `crackify.ui`: The user interface file for the application.
- `main.py`: The main Python script for running the application.
- `segment_engine.py`: Handles the segmentation logic.
- `widgets.py`: Defines Pyside6 widgets and UI components.

## Topics
- Segmentation
- Crack detection
- SAHI
- Construction-site management
- Orthophotos
- YOLOv8&#8203;``【oaicite:1】``&#8203;

## Installation
1. Clone the repository:
```
git clone https://github.com/s-du/WhatTheCrack
```

2. Navigate to the app directory:
```
cd WhatTheCrack
```
3. (Optional) Install and activate a virtual environment

   
4. Install the required dependencies:
```
pip install -r requirements.txt
```

5. Run the app:
```
python main.py
```
Note: By default, the app will run YOLO on cpu, except if there is an available CUDA environment (and associated pyTorch installation)

## Usage
(Coming soon)

## Contributing
Contributions to the WhatTheCrack App are welcome! If you find any bugs, have suggestions for new features, or would like to contribute enhancements, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make the necessary changes and commit them.
4. Push your changes to your fork.
5. Submit a pull request describing your changes.

## License
(Information about the project's license, if applicable.)

## Acknowledgements
(Credits to any contributors, third-party libraries, or other resources used in the project.)

## Languages
- Python&#8203;``【oaicite:0】``&#8203;

(Note: Please update each section with specific details pertinent to the WhatTheCrack project.)