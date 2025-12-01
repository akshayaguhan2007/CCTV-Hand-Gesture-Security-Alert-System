from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, Flask is running!"

if __name__ == '__main__':
    print("🔄 Starting minimal Flask server...")
    app.run(debug=True)
