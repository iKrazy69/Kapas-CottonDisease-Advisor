import os
import re
import wave
import tempfile
from pathlib import Path
import sounddevice as sd
from scipy.io import wavfile

try:
    from piper.voice import PiperVoice
except Exception:
    from piper import PiperVoice

from speech_text import speech_clauses

BASE_DIR = Path(__file__).resolve().parent
TTS_MODEL_DIR = BASE_DIR / "tts_models"

# --- DEBUG: This will print the folder path in your terminal ---
print(f"DEBUG: Looking for models in: {TTS_MODEL_DIR}")
if not TTS_MODEL_DIR.exists():
    print(f"ERROR: The folder 'tts_models' does not exist at {TTS_MODEL_DIR}")
# ---------------------------------------------------------------

PIPER_MODELS = {
    "en": TTS_MODEL_DIR / "en_US-lessac-medium.onnx",
    "hi": TTS_MODEL_DIR / "hi_IN-pratham-medium.onnx",
}

VOICE_CACHE = {}


def clean_tts_text(text, lang_code=None):
    """Plain spoken text: no markdown, source references, symbols or punctuation (see speech_text.py)."""
    return " ".join(c for c, _ in speech_clauses(text, lang_code or "en"))


def normalize_lang_code(lang_code):
    if not lang_code:
        return None

    if isinstance(lang_code, list):
        lang_code = lang_code[0]

    lang_code = str(lang_code).strip().lower()

    lang_map = {
        "english": "en",
        "en-us": "en",
        "en_in": "en",
        "en-in": "en",
        "en": "en",

        "hindi": "hi",
        "hi-in": "hi",
        "hi_in": "hi",
        "hi": "hi",
    }

    return lang_map.get(lang_code, lang_code)


def detect_language_from_text(text):
    # Hindi / Devanagari Unicode range
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"

    return "en"


def get_final_language(text, lang_code=None):
    lang_code = normalize_lang_code(lang_code)

    if lang_code in ["en", "hi"]:
        return lang_code

    return detect_language_from_text(text)


def get_piper_voice(lang_code):
    model_path = PIPER_MODELS.get(lang_code)

    if model_path is None:
        print(f"No Piper model configured for language: {lang_code}")
        return None

    if not model_path.exists():
        print(f"Piper model not found: {model_path}")
        return None

    config_path = Path(str(model_path) + ".json")
    if not config_path.exists():
        print(f"Piper config not found: {config_path}")
        return None

    if lang_code not in VOICE_CACHE:
        print(f"Loading Piper voice: {lang_code}")
        VOICE_CACHE[lang_code] = PiperVoice.load(str(model_path))

    return VOICE_CACHE[lang_code]


def write_speech(voice, clauses, wav_path):
    """Synthesise each clause on its own and write real silence between them.

    No punctuation is ever given to Piper, so it cannot read commas, full stops or symbols aloud.
    If this Piper version rejects the piece-by-piece call, fall back to one pass over the same
    punctuation-free text (flatter rhythm, but still nothing spoken that should not be).
    """
    try:
        with wave.open(str(wav_path), "wb") as wav_file:
            rate = int(voice.config.sample_rate)
            for i, (clause, pause) in enumerate(clauses):
                voice.synthesize_wav(clause, wav_file, set_wav_format=(i == 0))
                if pause > 0 and i < len(clauses) - 1:
                    wav_file.writeframes(b"\x00\x00" * int(rate * pause))
        return
    except Exception as e:
        print("Piece-by-piece speech failed, using one pass:", e)
    with wave.open(str(wav_path), "wb") as wav_file:
        voice.synthesize_wav(" ".join(c for c, _ in clauses), wav_file)


def play_wav(wav_path):
    sample_rate, audio_data = wavfile.read(str(wav_path))
    sd.play(audio_data, sample_rate)
    sd.wait()


def speak_text(text, lang_code=None):
    if not text:
        return

    lang_code = get_final_language(str(text), lang_code)
    clauses = speech_clauses(text, lang_code)

    if not clauses:
        return

    print("\nDetected TTS language:", lang_code)
    print("\nSpeaking text:")
    print(" | ".join(c for c, _ in clauses))

    voice = get_piper_voice(lang_code)

    if voice is None:
        print("TTS failed because Piper voice/model is missing.")
        return

    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    wav_path = Path(wav_path)

    try:
        write_speech(voice, clauses, wav_path)

        play_wav(wav_path)

        print("Speaking completed.")

    except Exception as e:
        print("Piper TTS error:", e)

    finally:
        try:
            wav_path.unlink()
        except Exception:
            pass

def save_audio_file(text, output_path, lang_code=None):
    """Generates the Piper TTS audio and saves it to a file for the web app."""
    if not text:
        return False

    lang_code = get_final_language(str(text), lang_code)
    clauses = speech_clauses(text, lang_code)
    if not clauses:
        return False

    print(f"Generating Web Audio (Language: {lang_code})...")
    voice = get_piper_voice(lang_code)

    if voice is None:
        print("TTS failed because Piper voice/model is missing.")
        return False

    try:
        write_speech(voice, clauses, output_path)
        return True
    except Exception as e:
        print("Piper TTS error:", e)
        return False