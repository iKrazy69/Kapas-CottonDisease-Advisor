# -*- coding: utf-8 -*-
"""
Fixed Hindi -> English list of cotton crop terms, used before the local model translates a Hindi question.

Why: the 8B model translated "टिंडा सड़न" as "Tinda rot", "जीवाणु पत्ती झुलसा" as "cotton leaf curl disease" and
"काली फफूंद" as "black spot disease", so the search found nothing and the app said the guide had no answer.
Here the known terms are swapped for the English words the guide itself uses BEFORE the model sees the question,
and the model is told to leave English words alone. If a swapped term is still missing from the model's output,
translator.py adds it at the end so the search always gets it.

STATUS: NOT checked by a native Hindi speaker or a cotton expert. It was written after looking at
the benchmark's failed Hindi questions, so benchmark Hindi results after this change are not a clean test of the
translation step. Add terms here; longer phrases are matched before shorter ones, so "टिंडा सड़न" wins over "टिंडा".
"""

import re
import unicodedata

# (English as the guide writes it, [Hindi spellings]).  Spellings are compared without nukta (ज़ = ज, फ़ = फ).
TERMS = [
    # ---------------------------------------------------------------- diseases
    ('fungal boll rot', ['फफूंद जनित टिंडा सड़न', 'फफूंदी जनित टिंडा सड़न', 'फफूंदजनित टिंडा सड़न', 'कवक जनित टिंडा सड़न']),
    ('boll rot', ['टिंडा सड़न', 'टिण्डा सड़न', 'टिंडे की सड़न', 'टिंडों की सड़न', 'टिंडा गलन', 'टिंडे का सड़न', 'गूलर सड़न']),
    ('root rot', ['जड़ सड़न', 'जड़ गलन', 'जड़ों की सड़न', 'जड़ का सड़न', 'जड़ों का सड़ना']),
    ('bacterial leaf blight', ['जीवाणु पत्ती झुलसा', 'जीवाणुजनित पत्ती झुलसा', 'जीवाणु जनित पत्ती झुलसा', 'जीवाणुज पत्ती झुलसा']),
    ('bacterial blight', ['जीवाणु झुलसा', 'जीवाणुजनित झुलसा', 'जीवाणु जनित झुलसा', 'जीवाणुज झुलसा', 'जीवाणु अंगमारी']),
    ('leaf curl', ['पत्ती मरोड़', 'पत्ता मरोड़', 'पत्ती मोड़क', 'पत्तियों का मुड़ना', 'लीफ कर्ल']),
    ('sooty mould', ['काली फफूंद', 'काली फफूंदी', 'सूटी मोल्ड', 'कज्जली फफूंद']),
    ('grey mildew', ['ग्रे मिल्ड्यू', 'ग्रे मिलड्यू', 'धूसर फफूंद', 'दहिया रोग']),
    ('Myrothecium leaf spot', ['मायरोथीसियम पत्ती धब्बा', 'मायरोथेसियम पत्ती धब्बा', 'मायरोथीसियम पत्ती के धब्बे', 'मायरोथेसियम पत्ती के धब्बे']),
    ('Myrothecium', ['मायरोथीसियम', 'मायरोथेसियम']),
    ('Alternaria leaf spot', ['अल्टरनेरिया पत्ती धब्बा', 'आल्टरनेरिया पत्ती धब्बा']),
    ('Alternaria', ['अल्टरनेरिया', 'आल्टरनेरिया']),
    ('leaf spot', ['पत्ती धब्बा', 'पत्ती के धब्बे', 'पत्तियों पर धब्बे']),
    ('Fusarium wilt', ['फ्यूजेरियम उकठा', 'फ्यूजेरियम विल्ट', 'फ्यूजेरियम म्लानि']),
    ('wilt', ['उकठा', 'म्लानि']),
    ('anthracnose', ['एन्थ्रेक्नोज', 'एन्थ्राक्नोज', 'एंथ्रेक्नोज']),
    ('tobacco streak', ['तंबाकू स्ट्रीक', 'टोबैको स्ट्रीक']),
    # ---------------------------------------------------------------- pests
    ('pink bollworm', ['गुलाबी सुंडी', 'गुलाबी इल्ली', 'गुलाबी बॉलवर्म']),
    ('spotted bollworm', ['चितकबरी सुंडी', 'चित्तीदार सुंडी', 'चितकबरी इल्ली']),
    ('American bollworm', ['अमेरिकन सुंडी', 'अमेरिकी सुंडी']),
    ('whitefly', ['सफेद मक्खी', 'सफेद मक्खियों', 'सफेद मक्खियाँ', 'व्हाइटफ्लाई']),
    ('jassid', ['जैसिड', 'हरा तेला', 'तेला', 'हरा फुदका', 'फुदका']),
    ('aphid', ['माहू', 'चेपा', 'एफिड']),
    ('thrips', ['थ्रिप्स']),
    ('mealybug', ['मिलीबग', 'मीलीबग', 'चूर्णी मत्कुण']),
    ('dusky cotton bug', ['डस्की कॉटन बग']),
    ('stem weevil', ['तना घुन']),
    ('mites', ['माइट', 'माइट्स', 'लाल मकड़ी']),
    ('termites', ['दीमक']),
    # ---------------------------------------------------------------- practices and terms
    ('acid delinting', ['अम्ल से रेशा हटाना', 'अम्ल द्वारा रेशा हटाना', 'अम्ल से रेशा निकालना', 'एसिड डिलिंटिंग', 'एसिड डीलिंटिंग']),
    ('seed treatment', ['बीज उपचार', 'बीजोपचार']),
    ('economic threshold', ['आर्थिक हानि स्तर', 'आर्थिक क्षति स्तर', 'आर्थिक दहलीज', 'आर्थिक क्षति सीमा']),
    ('yellow sticky traps', ['पीले चिपचिपे जाल', 'पीला चिपचिपा जाल', 'पीले चिपचिपे ट्रैप', 'पीले स्टिकी ट्रैप', 'येलो स्टिकी ट्रैप']),
    ('farmyard manure', ['गोबर की खाद', 'गोबर खाद', 'सड़ी गोबर की खाद']),
    ('drenching', ['ड्रेंचिंग']),
    ('desi cotton', ['देसी कपास', 'देशी कपास']),
    ('border rows', ['बॉर्डर पंक्तियाँ', 'बॉर्डर पंक्तियों', 'बॉर्डर लाइन']),
    ('fungicide', ['फफूंदनाशक', 'फफूंदीनाशक', 'कवकनाशी']),
    ('days after sowing', ['बुवाई के बाद दिन']),
    # ---------------------------------------------------------------- chemicals and bio-agents (guide spelling)
    ('Carbendazim', ['कार्बेन्डाजिम', 'कार्बेंडाजिम', 'कार्बेन्डेजिम', 'कार्बेंडेजिम']),
    ('Mancozeb', ['मैंकोजेब', 'मैन्कोजेब', 'मेंकोजेब', 'मैंकोज़ेब']),
    ('Propineb', ['प्रोपिनेब', 'प्रोपीनेब']),
    ('Thiram', ['थिराम', 'थायरम', 'थीरम']),
    ('Carboxin', ['कार्बोक्सिन', 'कार्बोक्सीन']),
    ('Propiconazole', ['प्रोपिकोनाजोल', 'प्रोपिकोनाज़ोल', 'प्रोपीकोनाजोल']),
    ('Pyraclostrobin', ['पायराक्लोस्ट्रोबिन', 'पाइराक्लोस्ट्रोबिन']),
    ('Azoxystrobin', ['एजोक्सीस्ट्रोबिन', 'एज़ोक्सीस्ट्रोबिन']),
    ('Trichoderma', ['ट्राइकोडर्मा', 'ट्राईकोडर्मा']),
    ('Pseudomonas', ['स्यूडोमोनास', 'सूडोमोनास']),
    ('zinc sulphate', ['जिंक सल्फेट', 'जस्ता सल्फेट']),
    ('Imidacloprid', ['इमिडाक्लोप्रिड', 'इमिडाक्लोप्रिड']),
    ('Thiamethoxam', ['थायामेथोक्साम', 'थियामेथोक्साम']),
    ('Flonicamid', ['फ्लोनिकामिड']),
    ('Diafenthiuron', ['डायफेंथियूरॉन', 'डायफेन्थियूरॉन']),
    ('Profenofos', ['प्रोफेनोफॉस', 'प्रोफेनोफोस']),
    ('Spinosad', ['स्पिनोसैड']),
    ('Indoxacarb', ['इंडोक्साकार्ब']),
    ('neem', ['नीम']),
    # not in the guide, listed so the question is translated faithfully (the engine must still decline the dose)
    ('acephate', ['एसीफेट', 'एसिफेट']),
    ('monocrotophos', ['मोनोक्रोटोफॉस', 'मोनोक्रोटोफोस']),
    ('glyphosate', ['ग्लाइफोसेट']),
    # ---------------------------------------------------------------- formulation codes
    ('WP', ['डब्ल्यूपी', 'डब्लूपी', 'डब्ल्यू.पी.']),
    ('EC', ['ईसी', 'ई.सी.']),
    ('SC', ['एससी', 'एस.सी.']),
]

_NUKTA = '़'
_DEVA = 'ऀ-ॿ'


_NUKTA_LETTERS = set('कखगजडढफय')       # letters people write with or without the dot (ज़/ज, ड़/ड, फ़/फ)


def _norm(text):
    """NFC with every nukta removed: the key a match is looked up by."""
    return unicodedata.normalize('NFC', text or '').replace(_NUKTA, '')


def _loose(spelling):
    """Regex for a spelling that matches it with or without nukta dots."""
    out = []
    for ch in _norm(spelling):
        out.append(re.escape(ch))
        if ch in _NUKTA_LETTERS:
            out.append(_NUKTA + '?')
    return ''.join(out)


def _build():
    pairs = []
    for english, spellings in TERMS:
        for hi in spellings:
            pairs.append((_norm(hi), english))
    pairs.sort(key=lambda p: -len(p[0]))          # longest first
    alternation = '|'.join(_loose(h) for h, _ in pairs)
    # a term must not start or end in the middle of a Devanagari word (\b does not work with Hindi vowel signs)
    pattern = re.compile(f'(?<![{_DEVA}])(?:{alternation})(?![{_DEVA}])')
    return pattern, dict(pairs)


_PATTERN, _LOOKUP = _build()


def apply(text):
    """Swap known Hindi crop terms for English. Returns (new_text, [english terms used, in order, no repeats])."""
    found = []

    def repl(m):
        en = _LOOKUP[_norm(m.group(0))]
        if en not in found:
            found.append(en)
        return en

    out = _PATTERN.sub(repl, unicodedata.normalize('NFC', text or ''))
    for en in found:                               # "काली फफूंद (सूटी मोल्ड)" -> "sooty mould", not "sooty mould (sooty mould)"
        out = out.replace(f'{en} ({en})', en)
    return out, found


def _stem(word):
    """Rough English stem so "whiteflies" counts as "whitefly" and "drench" as "drenching"."""
    for end in ('ing', 'ies', 'es', 's', 'y'):
        if word.endswith(end) and len(word) - len(end) >= 4:
            return word[:-len(end)]
    return word


def missing_terms(english_text, terms):
    """The terms from apply() that the translated text lost (ignoring case, spaces, plurals and -ing)."""
    flat = re.sub(r'\s+', '', (english_text or '').lower())
    return [t for t in terms if not all(_stem(w) in flat for w in t.lower().split())]
