from flask import Flask, render_template
import speech_recognition as sr
import pyttsx3
import datetime
import os
import threading

# Google API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

app = Flask(__name__)

messages = []

# Only read permissions needed
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def speak(text):
    """Speak aloud + log message safely"""
    print("🤖 Alfred:", text)
    messages.append({"sender": "bot", "text": text})

    def run_tts():
        try:
            local_engine = pyttsx3.init()   # new engine per thread
            local_engine.setProperty("rate", 160)   # speech speed
            local_engine.setProperty("volume", 1.0) # max volume
            voices = local_engine.getProperty("voices")
            if voices:
                local_engine.setProperty("voice", voices[0].id)
            local_engine.say(text)
            local_engine.runAndWait()
            local_engine.stop()
        except Exception as e:
            print("TTS error:", e)

    threading.Thread(target=run_tts, daemon=True).start()


def listen():
    """Listen to mic and return recognized text"""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source, phrase_time_limit=5)
        try:
            return recognizer.recognize_google(audio).lower()
        except sr.UnknownValueError:
            return "sorry i did not understand that"
        except sr.RequestError as e:
            return f"speech service error: {e}"


def get_calendar_service():
    """Authenticate Google Calendar"""
    try:
        # Absolute path to credentials.json in D drive
        CREDENTIALS_PATH = r"D:\app\credentials.json"
        print("Looking for credentials.json at:", CREDENTIALS_PATH)

        if not os.path.exists(CREDENTIALS_PATH):
            speak(f"Credentials file not found at {CREDENTIALS_PATH}")
            return None

        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        speak(f"Calendar authentication failed: {e}")
        return None


def read_event_labels():
    """Fetch only event titles for this month"""
    service = get_calendar_service()
    if not service:
        return

    try:
        now = datetime.datetime.utcnow()
        start_month = now.replace(day=1)
        next_month = (start_month + datetime.timedelta(days=32)).replace(day=1)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_month.isoformat() + "Z",
            timeMax=next_month.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])

        if not events:
            speak("You have no events this month.")
        else:
            speak("Here are your events:")
            for event in events:
                speak(event.get('summary', "No Title"))
    except Exception as e:
        speak(f"Error fetching events: {e}")


@app.route("/")
def index():
    return render_template("index.html", messages=messages)


@app.route("/listen")
def voice_command():
    """Main Alfred voice commands"""
    command = listen()
    messages.append({"sender": "user", "text": command})

    if "attendance" in command:
        speak("Your attendance is 72 percent. Please attend more lectures.")
    elif "reminder" in command or "event" in command or "calendar" in command:
        read_event_labels()
    else:
        speak("Sorry, I can only help with attendance and events.")
    
    return render_template("index.html", messages=messages)


if __name__ == "__main__":
    app.run(debug=True)
