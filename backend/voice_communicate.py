import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import numpy as np
import ollama
from tts_piper import speak_text
from rag_engine import RAGEngine


print("Loading RAG Database...")
engine = RAGEngine()

def retrieve_context(query):
    chunks, metadatas, similarities = engine._retrieve_context(query)
    return "\n\n".join(chunks)

def generate_answer(question, context):
    return engine._generate_response(context, question)

# Translation logic
LLM_MODEL = "llama3.1:8b"
OUTPUT_LANGUAGE_INSTRUCTIONS = {
    "en": "Keep the answer in English.",
    "hi": "Translate the answer into simple Hindi using Devanagari script.",
    "ur": "Translate the answer into simple Urdu."
}

def translate_answer_to_user_language(answer, lang_code, lang_name):
    if not answer: return answer
    if lang_code == "en": return answer.strip()
    
    instruction = OUTPUT_LANGUAGE_INSTRUCTIONS.get(lang_code, f"Translate the answer into {lang_name}.")
    translation_prompt = f"""
    You are a translation assistant. Translate the following English answer into the user's language.
    User language: {lang_name}
    Language code: {lang_code}
    English answer: {answer}
    Instruction: {instruction}
    Rules: Only return the translated answer. No meta-commentary.
    """
    try:
        response = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": translation_prompt}], options={"temperature": 0.3})
        return response["message"]["content"].strip()
    except Exception as e:
        print("Translation failed:", e)
        return answer.strip()

SAMPLE_RATE = 16000
AUDIO_FILE = "user_question.wav"
WHISPER_MODEL_NAME = "small" 
MIC_DEVICE_INDEX = 0  # Changed to 0 for default Mac mic (change back to 2 if using earphones)

SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "ur": "Urdu"}

print("Loading Whisper speech-to-text model...")
whisper_model = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
print("Whisper model loaded.")

def record_audio(seconds=6):
    print(f"\nRecording for {seconds} seconds. Speak your question now...")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=MIC_DEVICE_INDEX)
    sd.wait()
    print("Audio peak volume:", np.max(np.abs(audio)))
    write(AUDIO_FILE, SAMPLE_RATE, audio)
    print("Recording completed.")
    return AUDIO_FILE

def speech_to_text(audio_path):
    segments, info = whisper_model.transcribe(
        audio_path, task="transcribe", beam_size=5, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500), condition_on_previous_text=False
    )
    
    text = "".join([segment.text.strip() + " " for segment in segments]).strip()
    detected_lang_code = info.language
    detected_lang_name = SUPPORTED_LANGUAGES.get(detected_lang_code, detected_lang_code)

    if detected_lang_code not in ["en", "hi", "ur"]:
        return text, "", detected_lang_code, detected_lang_name, info.language_probability

    if detected_lang_code == "en":
        rag_question = text
    else:
        translated_segments, _ = whisper_model.transcribe(
            audio_path, task="translate", beam_size=5, vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500), condition_on_previous_text=False
        )
        rag_question = "".join([seg.text.strip() + " " for seg in translated_segments]).strip()

    return text, rag_question, detected_lang_code, detected_lang_name, info.language_probability

def main():
    print("\nHi, I am your Voice RAG Assistant.")
    speak_text("Hi, I am your Voice RAG Assistant. Press enter and speak your question.", "en")

    while True:
        command = input("\nPress Enter for voice input or type exit: ").strip()
        if command.lower() in ["exit", "quit"]:
            speak_text("Voice chatbot stopped.", "en")
            break

        audio_path = record_audio(seconds=6)
        question, rag_question, lang_code, lang_name, confidence = speech_to_text(audio_path)

        if lang_code not in ["en", "hi", "ur"]:
            print(f"Detected unsupported language: {lang_name}")
            speak_text("Please speak only in English or Hindi.", "en")
            continue

        print(f"\nYou said: {question}")
        print(f"Question sent to RAG: {rag_question}")
        speak_text(f"You said: {question}", lang_code)

        try:
            context = retrieve_context(rag_question)
            answer = generate_answer(rag_question, context)
            final_answer = translate_answer_to_user_language(answer, lang_code, lang_name)

            print("\nFinal Answer:\n", final_answer)
            print("\n" + "=" * 80 + "\n")
            speak_text(final_answer, lang_code)

        except Exception as e:
            print(f"Error: {e}")
            speak_text("Something went wrong while processing your question. Please try again.", lang_code)

if __name__ == "__main__":
    main()