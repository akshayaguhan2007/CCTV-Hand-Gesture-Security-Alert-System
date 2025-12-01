import os
import sys
import logging

# Suppress all stderr output initially
class SuppressStderr:
    def __enter__(self):
        self.stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.stderr

# Suppress TensorFlow warnings completely
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['ABSL_LOGGING_VERBOSITY'] = '3'

import warnings
warnings.filterwarnings('ignore')

# Suppress absl warnings
logging.getLogger('absl').setLevel(logging.ERROR)

# Suppress specific TensorFlow Lite warnings
logging.getLogger('tensorflow').setLevel(logging.ERROR)

import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
import cv2

import mediapipe as mp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "yoursecretkey")

DATABASE = 'database.db'
CAPTURES_DIR = 'static/captures'
last_alert = None

os.makedirs(CAPTURES_DIR, exist_ok=True)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

def classify_gesture(hand_landmarks):
    # Simple gesture classification based on landmarks
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

    # Thumbs up: thumb tip above thumb ip, other fingers curled
    if thumb_tip.y < thumb_ip.y and index_tip.y > index_pip.y and middle_tip.y > middle_pip.y and ring_tip.y > ring_pip.y and pinky_tip.y > pinky_pip.y:
        return "Thumbs_Up"

    # Peace: index and middle extended, others curled
    if index_tip.y < index_pip.y and middle_tip.y < middle_pip.y and ring_tip.y > ring_pip.y and pinky_tip.y > pinky_pip.y:
        return "Peace"

    # Fist: all fingers curled
    if index_tip.y > index_pip.y and middle_tip.y > middle_pip.y and ring_tip.y > ring_pip.y and pinky_tip.y > pinky_pip.y:
        return "Fist"

    return "Unknown"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                gesture TEXT NOT NULL,
                confidence REAL NOT NULL
            )
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO users (id, username, password)
            VALUES (1, "admin", "admin123")
        ''')
        conn.commit()

init_db()

def log_gesture(gesture, confidence):
    global last_alert
    timestamp = datetime.now().isoformat(timespec='seconds')
    last_alert = f"⚠️ {gesture} Detected!"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO logs (timestamp, gesture, confidence) VALUES (?, ?, ?)',
            (timestamp, gesture, confidence)
        )
        conn.commit()

def gen_frames():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("❌ Webcam not accessible")
        return

    while True:
        success, frame = cap.read()
        if not success:
            print("❌ Failed to capture frame")
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(frame_rgb)

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                gesture = classify_gesture(hand_landmarks)
                if gesture != "Unknown":
                    log_gesture(gesture, 0.7)  # Log gesture detection with fixed confidence

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            print("❌ Failed to encode frame")
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
            user = cursor.fetchone()
        if user:
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
    if 'user' not in session:
        return redirect(url_for('login'))
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({'alert': last_alert})

@app.route('/logs')
def logs():
    if 'user' not in session:
        return redirect(url_for('login'))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM logs ORDER BY id DESC')
        rows = cursor.fetchall()
    return render_template('logs.html', rows=rows)

@app.route('/logs-data')
def logs_data():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM logs ORDER BY id DESC LIMIT 50')
        rows = cursor.fetchall()
    logs_list = []
    for row in rows:
        logs_list.append({
            'id': row['id'],
            'timestamp': row['timestamp'],
            'gesture': row['gesture'],
            'confidence': row['confidence']
        })
    return jsonify(logs_list)

@app.route('/stats')
def stats():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM logs')
        total_detections = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM logs WHERE timestamp > datetime("now", "-1 hour")')
        recent_activity = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM logs WHERE confidence > 0.5')
        high_confidence = cursor.fetchone()[0]
        detection_rate = (high_confidence / total_detections * 100) if total_detections > 0 else 0
    return jsonify({
        'total_detections': total_detections,
        'recent_activity': recent_activity,
        'detection_rate': round(detection_rate, 1),
        'system_status': 'online'
    })

@app.route('/clear-logs', methods=['POST'])
def clear_logs():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM logs')
        conn.commit()
    return jsonify({'message': 'Logs cleared successfully'})

if __name__ == '__main__':
    print("🚀 App started...")
    app.run(debug=True, host='0.0.0.0', port=5000)
