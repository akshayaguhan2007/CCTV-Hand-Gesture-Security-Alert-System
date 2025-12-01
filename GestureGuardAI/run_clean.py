#!/usr/bin/env python3
"""
Clean runner for GestureGuardAI that suppresses TensorFlow Lite warnings
"""
import os
import sys
import subprocess
import warnings

# Suppress all TensorFlow and absl warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs
os.environ['ABSL_LOGGING_VERBOSITY'] = '3'  # Suppress absl logs

# Suppress Python warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Suppress stderr completely for TensorFlow warnings
class SuppressStderr:
    def __init__(self):
        self.original_stderr = sys.stderr

    def __enter__(self):
        sys.stderr = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.original_stderr

def main():
    print("🚀 Starting GestureGuardAI with clean output...")

    # Change to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Run the app with suppressed stderr
    with SuppressStderr():
        try:
            # Import and run the Flask app
            from app import app
            print("✅ App loaded successfully")
            print("🌐 Starting Flask server on http://localhost:5000")
            app.run(debug=False, host='0.0.0.0', port=5000)
        except Exception as e:
            print(f"❌ Error starting app: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
