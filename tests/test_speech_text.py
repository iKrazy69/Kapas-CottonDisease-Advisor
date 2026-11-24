"""Checks that nothing like a symbol or punctuation mark can reach the speech engine.
Runs without Piper, a speaker or a microphone (those are replaced by small stand-ins)."""
import os, sys, types, wave, tempfile, unicodedata
BACK = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
sys.path.insert(0, BACK)
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)

from speech_text import speech_clauses, speech_text, PAUSE_COMMA, PAUSE_SENTENCE, PAUSE_PARAGRAPH

def only_speakable(s):
    """True when s has only letters, marks, digits, spaces, joiners, a dot inside a number, an apostrophe inside a word."""
    n = len(s)
    for i, ch in enumerate(s):
        cat = unicodedata.category(ch)
        if cat[0] in 'LMN' or ch == ' ' or ch in '‌‍': continue
        if ch == "'" and 0 < i < n - 1 and s[i-1].isalpha() and s[i+1].isalpha(): continue
        if ch == '.' and 0 < i < n - 1 and s[i-1].isdigit() and s[i+1].isdigit(): continue
        return False
    return True

# ---------- English answer as the app produces it ----------
EN = ("**Cotton leaf curl virus disease** is spread by whitefly (**Source 1**).\n\n"
      "- Rogue out and destroy infected plants early (Source 1).\n"
      "* Spray 2.5 ml/litre of a 5-10% solution; cost about ₹1,500 per acre.\n"
      "1. Keep fields weed-free, e.g. near borders... 🌱\n"
      "Signs: curling & thickened veins — see https://example.org/guide for more.\n"
      "## Note\n> Ask your KVK (Krishi Vigyan Kendra) before spraying.\n"
      "Sources: CICR_Illustrative_Guide_Cotton_2026.txt, other_guide_pdf")
cl = speech_clauses(EN, 'en')
spoken = ' | '.join(c for c, _ in cl)
print(spoken)
check('every clause is plain speakable text', all(only_speakable(c) for c, _ in cl), [c for c, _ in cl if not only_speakable(c)])
for bad in ['*', '(', ')', '#', '>', '_', 'Source', 'http', 'example.org', '.txt', 'CICR_', '%', '&', '/', '₹', '🌱', '—', '...', ';']:
    check(f'"{bad}" removed', bad not in spoken, spoken)
check('percent spoken as a word', '5 to 10 percent' in spoken, spoken)
check('unit slash becomes per', '2.5 ml per litre' in spoken, spoken)
check('decimal point kept inside number', '2.5' in spoken)
check('rupees and thousands comma', '1500 rupees' in spoken, spoken)
check('ampersand spoken as and', 'curling and thickened veins' in spoken, spoken)
check('e.g. spoken as words', 'for example' in spoken, spoken)
check('hyphenated word split', 'weed free' in spoken, spoken)
check('bullet / list markers not spoken', not any(c.startswith(('1 ', '- ', '* ')) for c, _ in cl), spoken)
check('source list line dropped', 'other guide' not in spoken and 'Illustrative' not in spoken, spoken)
check('KVK bracket text kept', 'Krishi Vigyan Kendra' in spoken, spoken)

# ---------- pauses ----------
p = speech_clauses('Spray early, then wait. Check again? Yes!', 'en')
check('pause after comma / full stop', p[0] == ('Spray early', PAUSE_COMMA) and p[1][1] == PAUSE_SENTENCE and p[2][1] == PAUSE_SENTENCE, p)
check('no trailing silence', p[-1][1] == 0.0, p)
p = speech_clauses('One line\n\nNext paragraph', 'en')
check('blank line gives a longer pause', p[0][1] == PAUSE_PARAGRAPH, p)
check('decimal point is not a sentence break', [c for c, _ in speech_clauses('Score is 0.30 today', 'en')] == ['Score is 0.30 today'])

# ---------- apostrophes and quotes ----------
t = speech_text('''Don't spray "late". It's 'fine' now.''', 'en')
check('apostrophe kept inside words only', t == "Don't spray late It's fine now", t)

# ---------- Hindi ----------
HI = ("**कॉटन लीफ कर्ल वायरस रोग** सफ़ेद मक्खी से फैलता है (स्रोत 1)। \n"
      "- संक्रमित पौधों को जल्दी उखाड़ें, और नष्ट करें (Source 2)।\n"
      "- ५०% नहीं, 5-10% घोल का छिड़काव करें; खर्च ₹1,500 प्रति एकड़।\n"
      "स्रोत: CICR_guide.txt")
hc = speech_clauses(HI, 'hi')
hs = ' | '.join(c for c, _ in hc)
print(hs)
check('hindi clauses are plain speakable text', all(only_speakable(c) for c, _ in hc), [c for c, _ in hc if not only_speakable(c)])
for bad in ['*', '(', ')', '।', '%', '₹', 'स्रोत', 'Source', '.txt', ';', ',']:
    check(f'hindi: "{bad}" removed', bad not in hs, hs)
check('hindi percent word', 'प्रतिशत' in hs, hs)
check('hindi keeps matras and nukta (canonical form)',
      unicodedata.normalize('NFC', 'सफ़ेद मक्खी') in hs and 'संक्रमित पौधों को जल्दी उखाड़ें' in unicodedata.normalize('NFC', hs), hs)
check('hindi danda gives a sentence pause', hc[0][1] == PAUSE_SENTENCE, hc)
check('joiners kept for conjuncts', '‍' in speech_text('क्‍ष', 'hi'))
check('web citation numbers [1] [2, 3] are not read out', speech_text('Whitefly spreads it [1]. Remove plants [2, 3].', 'en') == 'Whitefly spreads it Remove plants', speech_text('Whitefly spreads it [1]. Remove plants [2, 3].', 'en'))
check('empty / None input', speech_clauses('', 'en') == [] and speech_clauses(None, 'en') == [] and speech_clauses('***  --- ()', 'en') == [])
check('(From Source: ...) tail cut', speech_text('Spray late. (From Source: guide.txt) more', 'en') == 'Spray late', speech_text('Spray late. (From Source: guide.txt) more', 'en'))

# ---------- Through tts_piper with stand-ins for Piper / speaker ----------
for name in ('sounddevice',):
    sys.modules[name] = types.ModuleType(name)
piper = types.ModuleType('piper'); voice_mod = types.ModuleType('piper.voice')
class _PV: pass
voice_mod.PiperVoice = _PV; piper.PiperVoice = _PV
sys.modules['piper'] = piper; sys.modules['piper.voice'] = voice_mod
try:
    import scipy.io.wavfile  # noqa
except Exception:
    sc = types.ModuleType('scipy'); io_ = types.ModuleType('scipy.io'); wf = types.ModuleType('scipy.io.wavfile')
    io_.wavfile = wf; sc.io = io_
    sys.modules.update({'scipy': sc, 'scipy.io': io_, 'scipy.io.wavfile': wf})
import tts_piper

class Cfg: sample_rate = 22050
class FakeVoice:
    config = Cfg()
    def __init__(self, strict=True): self.calls = []; self.strict = strict
    def synthesize_wav(self, text, wav_file, syn_config=None, set_wav_format=True, **kw):
        if self.strict is False and 'set_wav_format' in kw or (self.strict is False and set_wav_format is not True):
            raise TypeError('old piper')
        self.calls.append(text)
        if set_wav_format:
            wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(22050)
        wav_file.writeframes(b'\x01\x00' * int(22050 * 0.1 * max(1, len(text.split()))))

fv = FakeVoice()
tts_piper.get_piper_voice = lambda lang: fv
out = os.path.join(tempfile.mkdtemp(), 'a.wav')
ok = tts_piper.save_audio_file(EN, out, 'en')
check('save_audio_file succeeds', ok and os.path.getsize(out) > 44)
check('engine never receives punctuation or symbols', fv.calls and all(only_speakable(c) for c in fv.calls), fv.calls)
with wave.open(out) as w:
    dur = w.getnframes() / w.getframerate()
words = sum(len(c.split()) for c in fv.calls)
silence = sum(p for _, p in speech_clauses(EN, 'en'))
check('wav length = speech + pauses', abs(dur - (words * 0.1 + silence)) < 0.05, (dur, words * 0.1 + silence))
check('language detected from Devanagari when none given', tts_piper.get_final_language('कपास', None) == 'hi')
fv2 = FakeVoice(); tts_piper.get_piper_voice = lambda lang: fv2
out2 = os.path.join(tempfile.mkdtemp(), 'h.wav')
check('hindi save works', tts_piper.save_audio_file(HI, out2, 'hi') and all(only_speakable(c) for c in fv2.calls))
# an older Piper that rejects set_wav_format: falls back to one clean pass
fv3 = FakeVoice(strict=False); tts_piper.get_piper_voice = lambda lang: fv3
out3 = os.path.join(tempfile.mkdtemp(), 'f.wav')
check('fallback still clean', tts_piper.save_audio_file(EN, out3, 'en') and all(only_speakable(c) for c in fv3.calls) and fv3.calls[-1] == tts_piper.clean_tts_text(EN, 'en'), fv3.calls)
check('nothing to say -> no audio', tts_piper.save_audio_file('*** ()', os.path.join(tempfile.mkdtemp(), 'x.wav'), 'en') is False)
check('clean_tts_text helper', tts_piper.clean_tts_text('**Hi**, (Source 1) there.', 'en') == 'Hi there')

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
