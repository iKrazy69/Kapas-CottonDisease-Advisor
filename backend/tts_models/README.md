# Voice models (Piper)

The spoken answers use two [Piper](https://github.com/rhasspy/piper) voices. They are about 60 MB each, so they are not stored in this repository. Download them into this folder:

```bash
cd backend/tts_models
curl -L -O https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -L -O https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
curl -L -O https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx
curl -L -O https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json
```

Without them the app still answers in text; only the read-aloud part is missing. Each voice has its own licence on the Piper voices page.
