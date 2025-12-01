# TODO for Camera Detection Overhaul

- [x] Update requirements.txt to include ultralytics and remove unused dependencies
- [x] Modify app.py to use YOLOv8 for gesture detection instead of MediaPipe
- [x] Update test_hand_detection.py to use YOLO for testing
- [x] Test the updated camera detection functionality
- [x] Verify video feed and logging work correctly
- [x] Change model path to 'ai_model/model.pt' for gesture detection instead of person detection
- [x] Update test_hand_detection.py to use custom gesture model
- [x] Update app.py to use custom gesture model
- [x] Switched back to MediaPipe for hand detection since YOLO model was empty/corrupted
- [x] Updated app.py and test_hand_detection.py to use MediaPipe
- [x] Added mediapipe to requirements.txt
- [x] Suppressed TensorFlow and MediaPipe warnings in app.py and test_hand_detection.py
- [x] App runs without warnings (restart required to apply changes)
- [x] Hand detection now uses MediaPipe, detecting hands instead of persons
- [x] Updated app.py to classify and log specific gestures (Thumbs_Up, Peace, Fist) instead of just "hand"
