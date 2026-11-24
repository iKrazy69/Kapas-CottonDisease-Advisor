"""
Voice recording and transcription handler
"""

import os
import logging
from pathlib import Path
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import numpy as np

from config import Config

logger = logging.getLogger(__name__)

SAMPLE_RATE = Config.WHISPER_SAMPLE_RATE

# Languages the rest of the pipeline can answer in (Piper voices exist for these).
SUPPORTED_LANGUAGES = ('en', 'hi')

# Whisper often labels spoken Hindi as Urdu. We have no Urdu TTS voice, so a
# detected 'ur' is treated as Hindi and re-transcribed with language='hi'.
LANGUAGE_ALIASES = {'ur': 'hi'}


class VoiceHandler:
    def __init__(self):
        logger.info('🚀 Initializing Voice Handler...')
        self.whisper_model = WhisperModel(
            Config.WHISPER_MODEL,
            device=Config.WHISPER_DEVICE,
            compute_type=Config.WHISPER_COMPUTE_TYPE
        )
        logger.info('✅ Whisper model loaded')

    def record_audio(self, seconds=6, device_index=None):
        """Record audio from microphone"""
        try:
            logger.info(f'🎤 Recording for {seconds} seconds...')

            audio = sd.rec(
                int(seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='int16',
                device=device_index
            )

            sd.wait()

            peak = np.max(np.abs(audio))
            logger.info(f'📊 Audio peak volume: {peak}')

            return audio

        except Exception as e:
            logger.error(f'❌ Recording failed: {str(e)}')
            raise

    def save_audio(self, audio, filename='temp_audio.wav'):
        """Save audio to file"""
        try:
            write(filename, SAMPLE_RATE, audio)
            logger.info(f'💾 Audio saved: {filename}')
            return filename
        except Exception as e:
            logger.error(f'❌ Save failed: {str(e)}')
            raise

    def _run_whisper(self, audio_path, task, language=None):
        """Run one faster-whisper pass and return (text, info)."""
        segments, info = self.whisper_model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            task=task,
            language=language,
            condition_on_previous_text=False
        )
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        return text, info

    def speech_to_text(self, audio_path):
        """
        Transcribe speech in the speaker's own language and also produce an
        English version for retrieval.

        Returns a dict:
            supported          False if the language is not English/Hindi
            language           'en' or 'hi' (language the answer should be spoken in)
            detected_language  raw code Whisper reported (for logging)
            language_probability  Whisper's language-detection probability
            text               transcript in the speaker's language
            english            English translation (same as text for English)
        """
        try:
            logger.info(f'🎙️ Transcribing: {audio_path}')

            # Pass 1: transcribe in whatever language Whisper detects.
            text, info = self._run_whisper(audio_path, task='transcribe', language=Config.WHISPER_LANGUAGE)
            detected = info.language
            probability = float(getattr(info, 'language_probability', 0.0) or 0.0)
            logger.info(f'Detected language: {detected} (p={probability:.2f})')

            language = LANGUAGE_ALIASES.get(detected, detected)

            if language not in SUPPORTED_LANGUAGES:
                logger.warning(f'❌ Unsupported language detected: {detected}')
                return {
                    'supported': False,
                    'language': language,
                    'detected_language': detected,
                    'language_probability': probability,
                    'text': '',
                    'english': ''
                }

            # Whisper called it Urdu: redo the transcription as Hindi so the
            # text comes out in Devanagari instead of Urdu script.
            if language != detected:
                logger.info(f"Treating detected '{detected}' as '{language}', re-transcribing")
                text, _ = self._run_whisper(audio_path, task='transcribe', language=language)

            # Pass 2 (non-English only): English translation for retrieval.
            if language == 'en':
                english = text
            else:
                english, _ = self._run_whisper(audio_path, task='translate', language=language)

            logger.info(f'✅ Transcript ({language}): "{text}"')
            logger.info(f'✅ English for retrieval: "{english}"')

            return {
                'supported': True,
                'language': language,
                'detected_language': detected,
                'language_probability': probability,
                'text': text,
                'english': english
            }

        except Exception as e:
            logger.error(f'❌ Transcription failed: {str(e)}')
            raise
