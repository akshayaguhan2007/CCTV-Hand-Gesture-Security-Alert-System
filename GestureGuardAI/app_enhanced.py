import os
import sys
from datetime import datetime, timedelta
import threading
import time
import json

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import warnings
warnings.filterwarnings('ignore')

# Flask and web imports
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
from flask_socketio import SocketIO, emit

# Computer vision imports
import cv2
import numpy as np

# Custom modules
from enhanced_detection import EnhancedHandDetector
from advanced_logger import AdvancedLogger
from config import config_manager, get_config
from notifications import notification_manager, notify_gesture_detected

# Initialize Flask app
app = Flask(__name__)
app.secret_key = get_config('security.session_secret_key', 'change_this_in_production')

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize components
detector = EnhancedHandDetector()
logger = AdvancedLogger()
notification_manager.add_notification_callback(handle_notification)

# Global variables
last_alert = None
system_status = "Initializing..."
detection_active = True
frame_capture_enabled = False

# System monitoring
system_stats = {
    'total_detections': 0,
    'active_sessions': 0,
    'system_uptime': datetime.now(),
    'last_detection_time': None
}

def handle_notification(notification):
    """Handle notifications from the notification system"""
    try:
        socketio.emit('notification', {
            'type': notification['type'],
            'message': notification['message'],
            'data': notification['data'],
            'priority': notification['priority'],
            'timestamp': notification['timestamp']
        })

        # Update system status
        if notification['type'] == 'gesture_detected':
            global last_alert
            last_alert = f"⚠️ {notification['data']['gesture']} Detected!"

            # Emit real-time update
            socketio.emit('gesture_detected', {
                'gesture': notification['data']['gesture'],
                'confidence': notification['data']['confidence'],
                'timestamp': notification['timestamp']
            })

    except Exception as e:
        print(f"Error handling notification: {e}")

def initialize_system():
    """Initialize the system components"""
    global system_status
    try:
        system_status = "Starting up..."

        # Start logging session
        logger.start_session()

        # Initialize camera
        system_status = "Initializing camera..."

        # Test camera access
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            system_status = "Camera not accessible"
            return False

        cap.release()
        system_status = "System ready"
        return True

    except Exception as e:
        system_status = f"Initialization error: {str(e)}"
        print(f"System initialization error: {e}")
        return False

def capture_frame_with_detection(frame, detections):
    """Capture frame with detection overlay"""
    if not frame_capture_enabled:
        return None

    try:
        # Create capture directory if it doesn't exist
        capture_dir = 'static/captures'
        os.makedirs(capture_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        filename = f"capture_{timestamp}.jpg"
        filepath = os.path.join(capture_dir, filename)

        # Add detection info to frame
        for detection in detections:
            if detection['gesture'] != "Unknown":
                # Draw bounding box
                bbox = detection['bbox']
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

                # Add gesture label
                cv2.putText(frame, f"{detection['gesture']} ({detection['confidence']:.2f})",
                           (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Save frame
        cv2.imwrite(filepath, frame)

        return filename

    except Exception as e:
        print(f"Error capturing frame: {e}")
        return None

def gen_frames():
    """Generate video frames with enhanced detection"""
    global system_stats, last_alert

    cap = cv2.VideoCapture(get_config('camera.camera_id', 0))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, get_config('camera.width', 640))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, get_config('camera.height', 480))
    cap.set(cv2.CAP_PROP_FPS, get_config('camera.fps', 30))

    if not cap.isOpened():
        print("❌ Webcam not accessible")
        return

    frame_count = 0
    last_log_time = datetime.now()

    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("❌ Failed to capture frame")
                break

            frame_count += 1

            # Skip frames for performance
            if frame_count % get_config('detection.frame_skip_rate', 1) != 0:
                continue

            # Detect hands
            detections, processed_frame = detector.detect_hands(frame)

            # Process detections
            for detection in detections:
                if detection['gesture'] != "Unknown" and detection_active:
                    # Log gesture
                    gesture_data = {
                        'gesture': detection['gesture'],
                        'confidence': detection['confidence'],
                        'hand_id': detection['hand_id'],
                        'bbox': detection['bbox'],
                        'center': detection['center'],
                        'landmarks': detection['landmarks'],
                        'metadata': {
                            'frame_number': frame_count,
                            'processing_time': datetime.now().isoformat()
                        }
                    }

                    logger.log_gesture(gesture_data)

                    # Send notification
                    notify_gesture_detected(
                        detection['gesture'],
                        detection['confidence'],
                        detection['hand_id']
                    )

                    # Update stats
                    system_stats['total_detections'] += 1
                    system_stats['last_detection_time'] = datetime.now()

            # Capture frame if enabled
            captured_frame = capture_frame_with_detection(processed_frame, detections)

            # Encode frame
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            if not ret:
                print("❌ Failed to encode frame")
                break

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    except Exception as e:
        print(f"Error in frame generation: {e}")
    finally:
        cap.release()

@app.route('/')
def index():
    if not get_config('security.enable_authentication', True):
        return render_template('index.html')

    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not get_config('security.enable_authentication', True):
        session['user'] = 'admin'
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == get_config('security.default_username', 'admin') and \
           password == get_config('security.default_password', 'admin123'):
            session['user'] = username
            return redirect(url_for('index'))
        else:
            error = "Invalid credentials"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/video_feed')
def video_feed():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return redirect(url_for('login'))
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({
        'alert': last_alert,
        'system_status': system_status,
        'detection_active': detection_active,
        'stats': system_stats
    })

@app.route('/logs')
def logs():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return redirect(url_for('login'))

    # Get recent logs from advanced logger
    logs_data = logger.get_recent_logs(limit=100)
    return render_template('logs.html', rows=logs_data)

@app.route('/logs-data')
def logs_data():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    logs_data = logger.get_recent_logs(limit=50)
    return jsonify(logs_data)

@app.route('/stats')
def stats():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # Get stats from advanced logger
    session_stats = logger.get_session_stats()
    system_stats = logger.get_session_stats()  # Overall stats

    return jsonify({
        'total_detections': system_stats.get('total_detections', 0),
        'recent_activity': system_stats.get('total_detections', 0),  # Placeholder
        'detection_rate': 100 if system_stats.get('total_detections', 0) > 0 else 0,
        'system_status': 'online',
        'session_stats': session_stats
    })

@app.route('/clear-logs', methods=['POST'])
def clear_logs():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    logger.clear_old_logs(days_to_keep=0)  # Clear all logs
    return jsonify({'message': 'Logs cleared successfully'})

@app.route('/export-logs', methods=['POST'])
def export_logs():
    if get_config('security.enable_authentication', True) and 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    format_type = request.form.get('format', 'csv')
    try:
        filepath = logger.export_logs(format_type=format_type)
        return jsonify({
            'message': 'Logs exported successfully',
            'filepath': filepath
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/toggle-detection', methods=['POST'])
def toggle_detection():
    global detection_active
    detection_active = not detection_active

    status = "enabled" if detection_active else "disabled"
    notification_manager.notify_system_status(f"Detection {status}")

    return jsonify({'detection_active': detection_active})

@app.route('/capture-frame', methods=['POST'])
def capture_frame():
    global frame_capture_enabled
    frame_capture_enabled = True

    # Reset after 1 second
    def reset_capture():
        time.sleep(1)
        global frame_capture_enabled
        frame_capture_enabled = False

    threading.Thread(target=reset_capture, daemon=True).start()

    return jsonify({'message': 'Frame capture triggered'})

@app.route('/system-info')
def system_info():
    return jsonify({
        'config_summary': config_manager.get_config_summary(),
        'detection_stats': detector.get_detection_stats(),
        'notification_stats': notification_manager.get_notification_stats(),
        'system_uptime': str(datetime.now() - system_stats['system_uptime'])
    })

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('system_status', {
        'status': system_status,
        'detection_active': detection_active,
        'stats': system_stats
    })

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('get_logs')
def handle_get_logs(data):
    limit = data.get('limit', 50)
    logs = logger.get_recent_logs(limit=limit)
    emit('logs_data', logs)

@socketio.on('clear_notifications')
def handle_clear_notifications():
    notification_manager.clear_notification_history()
    emit('notifications_cleared')

if __name__ == '__main__':
    print("🚀 Starting Enhanced GestureGuardAI...")

    # Initialize system
    if initialize_system():
        print("✅ System initialized successfully")
        print("🌐 Starting web server...")

        # Start the application
        socketio.run(
            app,
            host=get_config('server.host', '0.0.0.0'),
            port=get_config('server.port', 5000),
            debug=get_config('server.debug', False)
        )
    else:
        print("❌ System initialization failed")
        sys.exit(1)
