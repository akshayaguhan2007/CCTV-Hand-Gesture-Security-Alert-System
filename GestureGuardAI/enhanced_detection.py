import cv2
import numpy as np
import mediapipe as mp
from datetime import datetime, timedelta
import logging
from collections import deque
import json

class EnhancedHandDetector:
    def __init__(self, config=None):
        self.config = config or {
            'min_detection_confidence': 0.8,
            'min_tracking_confidence': 0.7,
            'gesture_stability_frames': 5,
            'max_hands': 2,
            'enable_gesture_classification': True
        }

        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=self.config['min_detection_confidence'],
            min_tracking_confidence=self.config['min_tracking_confidence'],
            max_num_hands=self.config['max_hands']
        )
        self.mp_draw = mp.solutions.drawing_utils

        # Gesture tracking
        self.gesture_history = deque(maxlen=self.config['gesture_stability_frames'])
        self.last_gesture = None
        self.gesture_start_time = None
        self.detection_log = []

        # Hand tracking data
        self.hand_tracking_data = {}

        self.logger = logging.getLogger(__name__)

    def classify_gesture(self, hand_landmarks):
        """Enhanced gesture classification with better accuracy"""
        if not hand_landmarks:
            return "No Hand", 0.0

        thumb_tip = hand_landmarks.landmark[4]
        thumb_ip = hand_landmarks.landmark[3]
        index_tip = hand_landmarks.landmark[8]
        index_pip = hand_landmarks.landmark[6]
        middle_tip = hand_landmarks.landmark[12]
        middle_pip = hand_landmarks.landmark[10]
        ring_tip = hand_landmarks.landmark[16]
        ring_pip = hand_landmarks.landmark[14]
        pinky_tip = hand_landmarks.landmark[20]
        pinky_pip = hand_landmarks.landmark[18]

        # Calculate finger states with improved logic
        fingers = []

        # Thumb
        thumb_extended = thumb_tip.x < thumb_ip.x if hand_landmarks.landmark[2].x < hand_landmarks.landmark[5].x else thumb_tip.x > thumb_ip.x
        fingers.append(thumb_extended)

        # Index finger
        fingers.append(index_tip.y < index_pip.y)

        # Middle finger
        fingers.append(middle_tip.y < middle_pip.y)

        # Ring finger
        fingers.append(ring_tip.y < ring_pip.y)

        # Pinky
        fingers.append(pinky_tip.y < pinky_pip.y)

        # Gesture classification with confidence scoring
        confidence = 0.9  # Base confidence

        # Thumbs up: thumb extended, others curled
        if fingers == [True, False, False, False, False]:
            return "Thumbs_Up", confidence

        # Peace/Victory: index and middle extended, others curled
        if fingers == [False, True, True, False, False]:
            return "Peace", confidence

        # Fist: all fingers curled
        if fingers == [False, False, False, False, False]:
            return "Fist", confidence

        # Open hand: all fingers extended
        if fingers == [True, True, True, True, True]:
            return "Open_Hand", confidence * 0.8

        # Pointing: only index extended
        if fingers == [False, True, False, False, False]:
            return "Pointing", confidence * 0.7

        # OK gesture: thumb and index form circle, others extended
        if fingers == [True, True, True, True, True]:
            # Additional check for OK gesture
            thumb_index_distance = np.sqrt((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)
            if thumb_index_distance < 0.05:  # Close proximity
                return "OK", confidence * 0.6

        return "Unknown", confidence * 0.3

    def detect_hands(self, frame):
        """Enhanced hand detection with tracking"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(frame_rgb)

        current_time = datetime.now()
        detections = []

        if result.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                # Draw landmarks
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                # Get gesture classification
                gesture, confidence = self.classify_gesture(hand_landmarks)

                # Calculate hand bounding box
                h, w, c = frame.shape
                x_min, y_min = w, h
                x_max, y_max = 0, 0

                for landmark in hand_landmarks.landmark:
                    x, y = int(landmark.x * w), int(landmark.y * h)
                    x_min, y_min = min(x_min, x), min(y_min, y)
                    x_max, y_max = max(x_max, x), max(y_max, y)

                # Add padding to bounding box
                padding = 20
                x_min = max(0, x_min - padding)
                y_min = max(0, y_min - padding)
                x_max = min(w, x_max + padding)
                y_max = min(h, y_max + padding)

                # Calculate hand center
                center_x = (x_min + x_max) // 2
                center_y = (y_min + y_max) // 2

                detection = {
                    'hand_id': hand_idx,
                    'gesture': gesture,
                    'confidence': confidence,
                    'bbox': (x_min, y_min, x_max, y_max),
                    'center': (center_x, center_y),
                    'timestamp': current_time,
                    'landmarks': [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
                }

                detections.append(detection)

                # Track gesture stability
                self.gesture_history.append(gesture)
                if len(self.gesture_history) == self.config['gesture_stability_frames']:
                    if len(set(self.gesture_history)) == 1:  # All gestures are the same
                        if gesture != self.last_gesture:
                            self.last_gesture = gesture
                            self.gesture_start_time = current_time
                            self.logger.info(f"Stable gesture detected: {gesture} (confidence: {confidence:.2f})")

        return detections, frame

    def get_gesture_stability(self):
        """Get gesture stability information"""
        if not self.gesture_history:
            return "No gesture", 0.0

        # Calculate most common gesture in recent history
        gesture_counts = {}
        for gesture in self.gesture_history:
            gesture_counts[gesture] = gesture_counts.get(gesture, 0) + 1

        most_common = max(gesture_counts, key=gesture_counts.get)
        stability = gesture_counts[most_common] / len(self.gesture_history)

        return most_common, stability

    def reset_tracking(self):
        """Reset gesture tracking"""
        self.gesture_history.clear()
        self.last_gesture = None
        self.gesture_start_time = None
        self.hand_tracking_data.clear()

    def get_detection_stats(self):
        """Get detection statistics"""
        return {
            'total_detections': len(self.detection_log),
            'current_gesture': self.last_gesture,
            'gesture_stability': len(self.gesture_history) / self.config['gesture_stability_frames'] if self.gesture_history else 0,
            'last_detection_time': self.gesture_start_time.isoformat() if self.gesture_start_time else None
        }
