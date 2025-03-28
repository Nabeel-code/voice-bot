from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS
import os
import uuid
import speech_recognition as sr
import threading
import atexit
from werkzeug.serving import make_server
import time

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuration
client = OpenAI(api_key="OPEN_API_KEY")  # Replace with your actual key
PORT = 5000

# Your personalized responses
PERSONAL_RESPONSES = {
    "What should we know about your life story in a few sentences?": 
        "I've always been curious about how things work and how to make them better. "
        "My journey has been shaped by a love for problem-solving, creativity, and a "
        "constant drive to grow. Whether it's learning something new, tackling challenges, "
        "or finding ways to make an impact, I thrive on pushing boundaries. Along the way, "
        "I've discovered that the most meaningful progress happens when innovation meets purpose.",
    
    "What's your #1 superpower?": 
        "I adapt quickly to new challenges and find creative ways to optimize processes.",
    
    "What are the top 3 areas you'd like to grow in?": 
        "1. Advanced AI applications in decision-making and automation.\n"
        "2. Leadership and influencing skills to drive impactful projects.\n"
        "3. Balancing deep technical expertise with high-level strategic thinking.",
    
    "What misconception do your coworkers have about you?": 
        "That I only care about numbers, but I also value the human side and technology.",
    
    "How do you push your boundaries and limits?": 
        "I constantly seek new challenges, whether it's tackling complex AI problems, "
        "learning new techniques, or stepping outside my comfort zone in leadership roles. "
        "I experiment with different problem-solving approaches and stay updated with "
        "the latest advancements in AI and other technologies."
}

# Server setup
class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server('0.0.0.0', PORT, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print(f"Server starting on port {PORT}")
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

def start_server():
    global server
    server = ServerThread(app)
    server.start()
    atexit.register(server.shutdown)

# Audio functions
def setup_audio():
    os.makedirs('static/audio', exist_ok=True)
    # Clean old audio files
    for file in os.listdir('static/audio'):
        if file.endswith('.mp3') or file.endswith('.wav'):
            os.remove(f'static/audio/{file}')

def speech_to_text(audio_data):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 4000
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8
    
    try:
        with sr.AudioFile(audio_data) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language="en-US")
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return None
    except Exception as e:
        print(f"Speech recognition error: {str(e)}")
        return None

def text_to_speech(text):
    filename = f"audio/response_{uuid.uuid4().hex}.mp3"
    os.makedirs('static/audio', exist_ok=True)
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(f'static/{filename}')
    return filename

def generate_response(question):
    if question in PERSONAL_RESPONSES:
        return PERSONAL_RESPONSES[question]
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    start_time = time.time()
    
    if 'audio' in request.files:
        audio_file = request.files['audio']
        temp_path = f"static/audio/temp_{uuid.uuid4().hex}.wav"
        audio_file.save(temp_path)
        question = speech_to_text(temp_path)
        os.remove(temp_path)
        
        if not question:
            return jsonify({"error": "Couldn't understand audio. Please try again."}), 400
    else:
        question = request.json.get('question')
        if not question:
            return jsonify({"error": "No question provided"}), 400
    
    response_text = generate_response(question)
    audio_path = text_to_speech(response_text)
    
    print(f"Processing time: {time.time() - start_time:.2f} seconds")
    
    return jsonify({
        "question": question,
        "response_text": response_text,
        "audio_response": f"/static/{audio_path}"
    })
