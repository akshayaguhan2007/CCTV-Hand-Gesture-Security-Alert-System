from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
import sqlite3
from datetime import datetime
import os
import cv2
import mediapipe as mp

app = Flask(__name__)
app.secret_key = 'yoursecretkey'

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Dummy video_feed route for template compatibility
def gen_frames():
    print("📸 Starting camera stream...")
    cap = cv2.VideoCapture(0)
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
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()

DATABASE = 'database.db'
last_alert = None

def get_db_connection():
    return sqlite3.connect(DATABASE)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        gesture TEXT NOT NULL,
        confidence REAL NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    cursor.execute('INSERT OR IGNORE INTO users (id, username, password) VALUES (1, "admin", "admin123")')
    conn.commit()
    conn.close()

init_db()

def log_gesture(gesture, confidence):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (timestamp, gesture, confidence) VALUES (?, ?, ?)',
                   (datetime.now().isoformat(), gesture, confidence))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/logs')
def logs():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM logs ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return render_template('logs.html', rows=rows)

@app.route('/status')
def status():
    global last_alert
    return jsonify({'alert': last_alert})

# Update /video_feed route to stream video
@app.route('/video_feed')
def video_feed():
    if 'user' not in session:
        return redirect(url_for('login'))
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("🔄 Starting Flask server...")
    app.run(debug=True)
