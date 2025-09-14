import uuid
import threading
import os
import asyncio
from flask import Flask, request, make_response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
from thirdagent import agent_answer
import edge_tts

from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

app = Flask(__name__, static_url_path='/static')

# print("Flask app starting...",os.getenv("PORT"),os.getenv("NGROK_HOST"))

app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

# ====== Config ======
NGROK_URL = os.getenv("NGROK_HOST") # <-- replace with your ngrok host

SUPPORTED_BY_TWILIO = {"hi-IN", "te-IN", "bn-IN", "kn-IN", "ml-IN", "pa-IN", "en-IN"}  # adjust if needed

# ====== Helpers ======
def twiml_response(response_obj):
    r = make_response(str(response_obj))
    r.headers['Content-Type'] = 'text/xml'
    return r


@app.route("/media/<path:filename>", methods=["GET"])
def media(filename):
    file_path = os.path.join("static", filename)
    if not os.path.exists(file_path):
        return "File not found", 404

    if filename.endswith(".mp3"):
        return send_file(file_path, mimetype="audio/mpeg", as_attachment=False, conditional=True)
    else:
        return send_file(file_path, mimetype="audio/wav", as_attachment=False, conditional=True)


# Simple healthcheck for Twilio debugger sanity
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# ====== Welcome ======
@app.route("/voice", methods=['POST'])
def voice():
    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/set_language', method='POST')
    gather.say(
        "Welcome to Telemedicine. "
        "Press 1 for Hindi, "
        "2 for Marathi, "
        "3 for Tamil, "
        "4 for Telugu, "
        "5 for Bengali, "
        "6 for Kannada, "
        "7 for Malayalam, "
        "8 for Punjabi, "
        "9 for English.",
        language='en-IN'
    )
    response.append(gather)
    response.say("Sorry, we didn't get any input. Goodbye.", language='en-IN')
    response.hangup()
    return twiml_response(response)

# ====== Language Selection ======
@app.route("/set_language", methods=['POST'])
def set_language():
    digit_pressed = request.form.get('Digits')
    language_map = {
        '1': 'hi-IN', '2': 'mr-IN', '3': 'ta-IN', '4': 'te-IN', '5': 'bn-IN',
        '6': 'kn-IN', '7': 'ml-IN', '8': 'pa-IN', '9': 'en-IN',
    }
    language = language_map.get(digit_pressed)
    if not language:
        response = VoiceResponse()
        response.say("Invalid selection. Goodbye.", language='en-IN')
        response.hangup()
        return twiml_response(response)

    response = VoiceResponse()
    response.redirect(f'/ask_query?lang={language}')
    return twiml_response(response)

# ====== Ask Query ======
@app.route("/ask_query", methods=['GET', 'POST'])  # allow GET + POST
def ask_query():
    language = request.args.get('lang', 'en-IN')
    response = VoiceResponse()
    gather = Gather(
        input='speech',
        action=f'/process?lang={language}',
        method='POST',
        language=language
    )
    gather.say("Please ask your question now.", language=language)
    response.append(gather)
    response.pause(length=2)
    response.say("Sorry, I didn't hear anything. Goodbye.", language=language)
    response.hangup()
    return twiml_response(response)

# ====== Edge TTS ======
async def async_generate_tts(reply_text, voice, filename):
    tmp = os.path.join("static", filename + ".tmp")
    final = os.path.join("static", filename)
    try:
        communicate = edge_tts.Communicate(reply_text, voice)
        await communicate.save(tmp)  # Edge-TTS outputs wav if filename ends with .wav
        os.replace(tmp, final)
        app.logger.info(f"Edge-TTS saved: {final}")
    except Exception as e:
        app.logger.exception("Edge-TTS generation failed: %s", e)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def generate_tts(reply_text, lang_short, filename):
    voice_map = {
        "mr": "mr-IN-AarohiNeural",
        "hi": "hi-IN-SwaraNeural",
        "ta": "ta-IN-PallaviNeural",
        "te": "te-IN-ShrutiNeural",
        "bn": "bn-IN-TanishaaNeural",
        "kn": "kn-IN-SapnaNeural",
        "ml": "ml-IN-SobhanaNeural",
        "pa": "pa-IN-GaganNeural",
        "en": "en-IN-NeerjaNeural",
    }
    voice = voice_map.get(lang_short, "en-IN-NeerjaNeural")
    asyncio.run(async_generate_tts(reply_text, voice, filename))

# ====== Process ======
@app.route("/process", methods=['POST'])
def process():
    language = request.args.get('lang', 'en-IN')
    user_input = request.form.get('SpeechResult', 'No input')

    if user_input == "No input":
        reply_text = "I didn't catch that, please say again."
    else:
        reply_text = agent_answer(user_input, language=language)

    response = VoiceResponse()
    app.logger.info(f"User ({language}): {user_input}")

    # Generate WAV filename
    # filename = f"resp_{uuid.uuid4().hex}.wav"
    filename = f"resp_{uuid.uuid4().hex}.mp3"

    # Run TTS in background
    threading.Thread(
        target=generate_tts,
        args=(reply_text, language.split("-")[0], filename),
        daemon=True
    ).start()
    

    # Small wait, then redirect to play (we also have retry logic there)
    response.pause(length=3)
    response.redirect(f"{NGROK_URL}/play?file={filename}&lang={language}&attempt=0", method='POST')
    return twiml_response(response)

# ====== Play ======
@app.route("/play", methods=['GET', 'POST'])
def play():
    filename = request.args.get('file')
    language = request.args.get('lang', 'en-IN')
    attempt = int(request.args.get('attempt', '0'))
    file_path = os.path.join("static", filename)
    response = VoiceResponse()

    MAX_ATTEMPTS = 20  # allow up to ~20 seconds total wait (1s per attempt + initial pause)

    if os.path.exists(file_path):
        # Serve via /media to force Content-Type: audio/wav
        response.play(f"{NGROK_URL}/media/{filename}")
        # After playing, gather response
        gather = Gather(
            input='speech',
            action=f'{NGROK_URL}/process?lang={language}',
            method='POST',
            language=language if language in SUPPORTED_BY_TWILIO else 'en-IN'
        )
        gather.say("Please respond now.", language='en-IN')
        response.append(gather)
        return twiml_response(response)

    if attempt < MAX_ATTEMPTS:
        app.logger.info(f"play: file {filename} not ready, attempt {attempt}. Retrying...")
        response.pause(length=1)
        response.redirect(
            f"{NGROK_URL}/play?file={filename}&lang={language}&attempt={attempt+1}",
            method='POST'
        )
        return twiml_response(response)

    app.logger.warning(f"play: file {filename} not ready after {MAX_ATTEMPTS} attempts.")
    response.say("Sorry, I couldn't prepare the audio right now. Please try again later.", language='en-IN')
    response.hangup()
    return twiml_response(response)

# ====== Run ======
if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(debug=True, port=os.getenv("PORT"), host='0.0.0.0')
