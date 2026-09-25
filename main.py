"""Hand gesture tracking with MediaPipe + OpenCV.

Detects: closed hand (fist), 1-4 fingers, and open hand (5 fingers).
Designed to drive LEDs on a Raspberry Pi via a callback.
"""
import math
import os
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

GESTURES = {
    0: "closed_hand",
    1: "one_finger",
    2: "two_fingers",
    3: "three_fingers",
    4: "four_fingers",
    5: "open_hand",
}

# Landmark indices (tip, pip) for index, middle, ring, pinky
FINGER_JOINTS = [(8, 6), (12, 10), (16, 14), (20, 18)]
WRIST = 0


def ensure_model():
    """Download the MediaPipe hand landmarker model if it isn't present."""
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading hand model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def count_fingers(landmarks):
    """Count extended fingers from 21 hand landmarks.

    Uses distances from the wrist rather than raw x/y comparisons, so it works
    regardless of which hand is shown or how the hand is rotated.
    """
    wrist = landmarks[WRIST]
    count = 0

    for tip, pip in FINGER_JOINTS:
        if _dist(landmarks[tip], wrist) > _dist(landmarks[pip], wrist):
            count += 1

    # Thumb: extended if its tip is farther from the pinky base than its IP
    # joint is, and it isn't tucked against the index knuckle.
    palm_size = _dist(wrist, landmarks[9])
    thumb_out = _dist(landmarks[4], landmarks[17]) > _dist(landmarks[3], landmarks[17])
    thumb_away = _dist(landmarks[4], landmarks[5]) > 0.5 * palm_size
    if thumb_out and thumb_away:
        count += 1

    return count


def track_hand_gestures(on_gesture=None, camera_index=0, show_window=True, stable_frames=5):
    """Open the camera and track hand gestures until 'q' is pressed.

    on_gesture:    callback(gesture_name, finger_count) fired only when the
                   detected gesture changes and has been stable for
                   `stable_frames` frames. finger_count is None / gesture is
                   "no_hand" when no hand is visible.
    camera_index:  OpenCV camera index (0 = default camera / Pi camera via V4L2).
    show_window:   show a preview window (set False when running headless on the Pi).
    stable_frames: frames a gesture must persist before it's reported (debounce,
                   prevents LEDs flickering).
    """
    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=ensure_model()),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {camera_index}")

    current_gesture = None
    candidate, candidate_count = None, 0
    start = time.monotonic()

    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)  # mirror so it feels natural

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.monotonic() - start) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    fingers = count_fingers(landmarks)
                    gesture = GESTURES[fingers]
                    if show_window:
                        vision.drawing_utils.draw_landmarks(
                            frame,
                            landmarks,
                            vision.HandLandmarksConnections.HAND_CONNECTIONS,
                        )
                else:
                    fingers, gesture = None, "no_hand"

                # Debounce: only report a gesture once it's held steady
                if gesture == candidate:
                    candidate_count += 1
                else:
                    candidate, candidate_count = gesture, 1
                if candidate_count >= stable_frames and candidate != current_gesture:
                    current_gesture = candidate
                    if on_gesture:
                        on_gesture(current_gesture, fingers)

                if show_window:
                    cv2.putText(frame, current_gesture or "...", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
                    cv2.imshow("Hand Gestures", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    finally:
        cap.release()
        if show_window:
            cv2.destroyAllWindows()


def make_led_handler(pins=(17, 27, 22, 23, 24)):
    """Return an on_gesture callback that lights N LEDs for N fingers.

    Closed hand / no hand -> all off, open hand -> all on. Falls back to
    printing when not running on a Raspberry Pi (gpiozero unavailable).
    """
    try:
        from gpiozero import LED
        leds = [LED(p) for p in pins]
    except Exception as e:
        leds = None
        print(f"gpiozero not available ({type(e).__name__}: {e}) - "
              "printing gestures instead of driving LEDs")

    def handler(gesture, fingers):
        n = fingers or 0
        print(f"Gesture: {gesture} ({n} fingers)")
        if leds:
            for i, led in enumerate(leds):
                led.on() if i < n else led.off()

    return handler


if __name__ == "__main__":
    track_hand_gestures(on_gesture=make_led_handler())
