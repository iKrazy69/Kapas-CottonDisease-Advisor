"""
OPTIONAL typed-input support for Marathi, Gujarati, Telugu, Kannada, Tamil,
Bengali, Punjabi, Malayalam via AI4Bharat IndicTrans2 (distilled 200M, MIT).

Off by default (Config.ENABLE_INDICTRANS). NOT TESTED by the project author's
tooling: it needs the gated Hugging Face models, `transformers<5`, `torch` and
`IndicTransToolkit`, none of which could be run where this was written. Treat
the first run as a test, and check the translations with a native speaker
before showing it to anyone.

    pip install "transformers<5" torch IndicTransToolkit sentencepiece
    huggingface-cli login      # accept the model terms on both model pages
"""

import logging

from config import Config

logger = logging.getLogger(__name__)

FLORES = {
    'hi': 'hin_Deva', 'mr': 'mar_Deva', 'gu': 'guj_Gujr', 'te': 'tel_Telu',
    'kn': 'kan_Knda', 'ta': 'tam_Taml', 'bn': 'ben_Beng', 'pa': 'pan_Guru',
    'ml': 'mal_Mlym',
}

_models = {}


def available(lang_code):
    return bool(Config.ENABLE_INDICTRANS) and lang_code in FLORES


def _load(direction):
    if direction in _models:
        return _models[direction]
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from IndicTransToolkit import IndicProcessor
    name = Config.INDICTRANS_EN_INDIC if direction == 'en_indic' else Config.INDICTRANS_INDIC_EN
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True)
    model.eval()
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    model.to(device)
    _models[direction] = (tok, model, IndicProcessor(inference=True), device)
    return _models[direction]


def _translate(text, src, tgt, direction):
    import torch
    tok, model, ip, device = _load(direction)
    batch = ip.preprocess_batch([text], src_lang=src, tgt_lang=tgt)
    inputs = tok(batch, truncation=True, padding='longest', return_tensors='pt').to(device)
    with torch.no_grad():
        out = model.generate(**inputs, num_beams=5, max_length=512)
    decoded = tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
    return ip.postprocess_batch(decoded, lang=tgt)[0]


def to_english(text, lang_code):
    """Returns English text, or None on any failure."""
    try:
        return _translate(text, FLORES[lang_code], 'eng_Latn', 'indic_en') or None
    except Exception as e:
        logger.error(f'IndicTrans2 to-English failed: {e}')
        return None


def from_english(text, lang_code):
    """Returns text in lang_code, or None on any failure."""
    try:
        return _translate(text, 'eng_Latn', FLORES[lang_code], 'en_indic') or None
    except Exception as e:
        logger.error(f'IndicTrans2 from-English failed: {e}')
        return None
