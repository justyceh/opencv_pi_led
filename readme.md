# OPENCV + RASPBERRY PI + BREADBOARD LED CONTROL
- This project is one of my first embedded system projects that uses Mediapipe and Opencv to control the leds on a breadboard
- We use raspberry pi as our brain and the digital pins to interact with our circuit components


# Things i learned
- Current and power enters into an led through an anode (the long leg of a led) and exits through the cathode (the short leg)
- Resistors simply limit the current flowing into our components so we dont break them
- On bread boards on the power strip power will flow vertically, but on the middle of the board it flows horizontally (so offsetting where we place things in rows is a good practice)
- For raspberry pi gpizero library we use the number of the pin from the board layout not the physical pin number

```
python -m venv --system-site-packages venv
source venv/bin/activate
pip install mediapipe opencv-python
python main.py
```
