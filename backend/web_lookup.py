"""Internet fallback: when the loaded documents do not cover a question, look it up on the web.

How it works
  1. search the web (DuckDuckGo's plain HTML page; Wikipedia as a second try) - no account or key needed
  2. download the top pages and keep the paragraphs that match the question
  3. ask the local Llama model to answer ONLY from those excerpts, with [1] [2] markers
  4. return the answer together with the page links, so the person can open and check them

It never invents a source: if nothing useful is found, or the internet cannot be reached, it says so
and the caller falls back to "ask your KVK".

Check it on your own computer (needs internet):
    python backend/web_lookup.py "how does cotton leaf curl virus spread"
    python backend/web_lookup.py "how does cotton leaf curl virus spread" --ask      # also runs the Llama step
"""
import re
import sys
import json
import logging
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote

import requests

try:
    from config import Config
except Exception:            # lets the file run on its own
    class Config:
        WEB_TIMEOUT_SECONDS = 8
        WEB_MAX_PAGES = 3
        WEB_USER_AGENT = 'Mozilla/5.0'
        OLLAMA_PORT = 11434
        OLLAMA_MODEL = 'llama3.1:8b'
        OLLAMA_TIMEOUT = 120

logger = logging.getLogger(__name__)

NO_ANSWER = 'I could not find a reliable answer on the web.'
OFF_TOPIC = 'That is outside what I can help with here.'
MAX_PAGE_BYTES = 600_000
EXCERPT_CHARS = 1800

# Pages that rarely help, and sources that are better than a random blog.
_BLOCKED = ('facebook.', 'instagram.', 'pinterest.', 'youtube.', 'youtu.be', 'tiktok.', 'twitter.', 'x.com', 'linkedin.',
            'quora.', 'amazon.', 'flipkart.', 'indiamart.', 'olx.')
_TRUSTED = ('icar.', 'cicr.', 'kvk', '.gov.in', 'nic.in', 'fao.org', '.edu', '.ac.in', 'cabi.org', 'wikipedia.org',
            'extension.', 'apsnet.', 'ipm', 'agri', 'cotton')
_STOP = set('''a an the is are was were be been being do does did can could should would will shall may might must i me my we our
you your it its this that these those what which who whom when where why how to of in on at for from by with about into than
then so as and or but if not no yes please tell give show any some there here have has had get got use using used best
good way ways'''.split())


# ---------------------------------------------------------------- search
def keywords(question):
    words = re.findall(r"[A-Za-z0-9ऀ-ॿ']+", question or '')
    keep = [w for w in words if w.lower() not in _STOP and len(w) > 1]
    return keep


def search_query(question, extra=''):
    q = ' '.join(keywords(question))
    if 'cotton' not in (q + ' ' + extra).lower():
        q += ' cotton'
    return (q + ' ' + extra).strip()


class _DDGParser(HTMLParser):
    """Reads result links and snippets from html.duckduckgo.com/html."""

    def __init__(self):
        super().__init__()
        self.results, self._cur, self._mode = [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get('class') or '').split()
        if tag == 'a' and 'result__a' in cls:
            self._cur = {'title': '', 'url': a.get('href', ''), 'snippet': ''}
            self.results.append(self._cur)
            self._mode = 'title'
        elif tag in ('a', 'div', 'td') and 'result__snippet' in cls and self._cur is not None:
            self._mode = 'snippet'

    def handle_endtag(self, tag):
        if tag == 'a' and self._mode == 'title':
            self._mode = None
        elif tag in ('a', 'div', 'td') and self._mode == 'snippet':
            self._mode = None

    def handle_data(self, data):
        if self._mode and self._cur is not None:
            self._cur[self._mode] += data


def _real_url(href):
    """DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<encoded url>."""
    href = (href or '').strip()
    if href.startswith('//'):
        href = 'https:' + href
    p = urlparse(href)
    if 'duckduckgo.com' in p.netloc and p.path.startswith('/l/'):
        target = parse_qs(p.query).get('uddg', [''])[0]
        return unquote(target)
    return href


def parse_ddg(html):
    parser = _DDGParser()
    parser.feed(html or '')
    out = []
    for r in parser.results:
        url = _real_url(r['url'])
        host = urlparse(url).netloc.lower()
        if not url.startswith(('http://', 'https://')) or 'duckduckgo.com' in host:
            continue                      # ads and internal links
        out.append({'title': re.sub(r'\s+', ' ', r['title']).strip(), 'url': url,
                    'snippet': re.sub(r'\s+', ' ', r['snippet']).strip()})
    return out


def search_duckduckgo(query, timeout):
    r = requests.post('https://html.duckduckgo.com/html/', data={'q': query, 'kl': 'in-en'},
                      headers={'User-Agent': Config.WEB_USER_AGENT, 'Accept-Language': 'en-IN,en;q=0.9'}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f'DuckDuckGo answered HTTP {r.status_code}')
    results = parse_ddg(r.text)
    if not results:
        raise RuntimeError('DuckDuckGo returned no readable results (it may be blocking automated searches)')
    return results


def search_wikipedia(query, timeout, limit=3):
    """Second try: returns results that already carry their text (no page download needed)."""
    h = {'User-Agent': 'CottonVoiceRAG/1.0 (student project)'}
    r = requests.get('https://en.wikipedia.org/w/api.php', headers=h, timeout=timeout,
                     params={'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': limit, 'format': 'json'})
    r.raise_for_status()
    out = []
    for hit in r.json().get('query', {}).get('search', []):
        title = hit.get('title')
        t = requests.get('https://en.wikipedia.org/w/api.php', headers=h, timeout=timeout,
                         params={'action': 'query', 'prop': 'extracts', 'explaintext': 1, 'titles': title, 'format': 'json'})
        pages = (t.json().get('query', {}).get('pages') or {}).values()
        text = next((p.get('extract', '') for p in pages), '')
        if text:
            out.append({'title': title + ' - Wikipedia', 'url': 'https://en.wikipedia.org/wiki/' + title.replace(' ', '_'),
                        'snippet': re.sub(r'<[^>]+>', '', hit.get('snippet', '')), 'text': text})
    if not out:
        raise RuntimeError('Wikipedia returned nothing')
    return out


def _rank(results):
    def score(r):
        host = urlparse(r['url']).netloc.lower()
        if any(b in host for b in _BLOCKED):
            return 99
        return 0 if any(t in host or t in r['url'].lower() for t in _TRUSTED) else 1
    kept = [r for r in results if score(r) < 99]
    return sorted(kept, key=score)             # stable: search order inside each group


# ---------------------------------------------------------------- pages
class _TextParser(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'svg', 'button', 'iframe'}
    BLOCK = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'td', 'th', 'dd', 'dt', 'blockquote'}

    def __init__(self):
        super().__init__()
        self.paras, self._buf, self._skip = [], [], 0

    def _flush(self):
        t = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
        self._buf = []
        if len(t) >= 50:
            self.paras.append(t)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK or tag == 'br':
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)


def html_to_paragraphs(html):
    p = _TextParser()
    p.feed(html or '')
    p._flush()
    return p.paras


def fetch_paragraphs(url, timeout):
    r = requests.get(url, headers={'User-Agent': Config.WEB_USER_AGENT, 'Accept-Language': 'en-IN,en;q=0.9'},
                     timeout=timeout, stream=True)
    r.raise_for_status()
    ctype = r.headers.get('Content-Type', '')
    if 'html' not in ctype and 'text' not in ctype:
        raise RuntimeError(f'not a web page ({ctype or "unknown type"})')
    raw = b''
    for chunk in r.iter_content(65536):
        raw += chunk
        if len(raw) > MAX_PAGE_BYTES:
            break
    r.close()
    enc = r.encoding or 'utf-8'
    return html_to_paragraphs(raw.decode(enc, errors='replace'))


def best_excerpt(paragraphs, question, limit=EXCERPT_CHARS):
    """The paragraphs that share the most words with the question, kept in page order."""
    words = {w.lower() for w in keywords(question)}
    scored = []
    for i, p in enumerate(paragraphs):
        pl = p.lower()
        hits = sum(1 for w in words if w in pl)
        scored.append((hits, -i, i, p))
    chosen, used = [], 0
    for hits, _, i, p in sorted(scored, reverse=True):
        if hits == 0 and chosen:
            break
        if used + len(p) > limit and chosen:
            continue
        chosen.append((i, p[:limit]))
        used += len(p)
        if used >= limit:
            break
    return ' '.join(p for _, p in sorted(chosen))


# ---------------------------------------------------------------- rules before and after the language model
# The language model is not trusted to stay on topic or to keep doses out, so plain rules do both.
DOSE_MESSAGE = ('I do not give spray doses or mixing amounts from the internet. '
                'Please read the product label or ask your nearest Krishi Vigyan Kendra (KVK) or agriculture officer.')
DOSE_NOTE = 'Spray doses are not given from the internet: read the product label or ask your KVK.'
NEED_MORE = 'Which disease or pest do you mean? Please tell me its name, or send a photo of the leaf.'

# A question with none of these words (and no diagnosed photo) is not about farming.
_FARM = re.compile(
    r'\b(?:cotton|crops?|plants?|plantation|leaf|leaves|seeds?|seedlings?|soil|land|acres?|hectares?|fields?|farm\w*|agri\w*|'
    r'kharif|rabi|irrigat\w*|water\w*|fertili[sz]\w*|manure|urea|dap|compost|nutrients?|production|productivity|'
    r'pests?|insects?|\w*worms?|whitefl\w*|aphids?|jassids?|thrips|mites?|bugs?|weeds?|diseases?|blight|wilt|rot|mou?ld|virus|'
    r'fung\w*|bacteri\w*|mildew|anthracnose|spray\w*|pesticides?|insecticides?|fungicides?|herbicides?|weedicides?|'
    r'harvest\w*|sow\w*|nurser\w*|bt|bolls?|lint|flower\w*|roots?|stems?|branch\w*|buds?|picking|ginning|'
    r'drought|rain\w*|monsoon|kvk|icar|cicr|msp|mandi|kisan|subsid\w*|insurance|pmfby|tractor|rice|wheat|maize|sugarcane|'
    r'vegetables?|neem)\b', re.I)
_PRONOUN = re.compile(r'\b(?:it|its|this|that|these|those)\b', re.I)

# Chemicals, and words that ask "how much / how often".
_CHEM = re.compile(
    r'\b(?:spray\w*|pesticides?|insecticides?|fungicides?|herbicides?|weedicides?|chemicals?|poisons?|'
    r'\w*(?:phos|fos|cide|conazole|azole|prid|thrin|mectin|thion|dazim|zeb)|'
    r'glyphosate|acephate|atrazine|pendimethalin|paraquat|thiamethoxam|acetamiprid|emamectin|spinosad|fipronil|'
    r'diafenthiuron|flonicamid|buprofezin|dimethoate|carbofuran|streptocycline|mancozeb|copper oxychloride|'
    r'sulphur|sulfur|neem oil|pyrithiobac|quizalofop)\b', re.I)
_QTY = re.compile(
    r'\b(?:dose|doses|dosage|how much|how many (?:ml|mls|g|gm|grams?|kg|litres?|liters?)|quantity|amount|ratio|mix|mixing|mixed|'
    r'schedule|per (?:litre|liter|l|acre|hectare|ha|tank|pump)|ml|mls|grams?|gms?|kgs?|litres?|liters?)\b', re.I)

# An amount of something to put on the crop: "2 g/L", "5 ml in 1 litre", "50 kg of urea", "@ 2 ml", "500 ppm".
_NUM = r'\d+(?:[.,]\d+)?(?:\s*(?:-|–|—|to)\s*\d+(?:[.,]\d+)?)?'
_UNIT = r'(?:kgs?|mg|mls?|millilit(?:re|er)s?|gms?|grams?|g|l|lit|litres?|liters?|cc|ppm)'
_DOSE_PER = re.compile(r'(?<![\w.])' + _NUM + r'\s*' + _UNIT + r'\b\s*(?:/|per\b|in\b)', re.I)
_DOSE_RATE = re.compile(r'(?<![\w.])' + _NUM + r'\s*' + _UNIT + r'\b[^.;\n]{0,25}?(?:/|\bper\b)\s*(?:\d+\s*)?(?:acre|hectare|ha|l|litre|liter|plant|tank|pump)\b', re.I)
_SMALL = r'(?:mls?|millilit(?:re|er)s?|gms?|grams?|mg|cc|g)'
# grams or millilitres per litre / kg / area: always a dose, even for a bio-agent such as Trichoderma
_DOSE_SMALL = re.compile(r'(?<![\w.])' + _NUM + r'\s*' + _SMALL + r'\b\s*(?:/|per\b|in\b)\s*(?:\d+(?:[.,]\d+)?\s*)?'
                         r'(?:kgs?|l|lit|litres?|liters?|ha|hectare|acre|plant|tank|pump|ml|g)\b', re.I)
_DOSE_OF = re.compile(r'(?<![\w.])' + _NUM + r'\s*(?:kgs?|mg|mls?|gms?|grams?|g|cc)\b\s+of\b', re.I)
_DOSE_PPM = re.compile(r'(?<![\w.])' + _NUM + r'\s*ppm\b', re.I)
_DOSE_PCT = re.compile(r'(?<![\w.])' + _NUM + r'\s*%\s*(?:solution|spray|emulsion|ec|sc|wp|wg|sl)\b', re.I)
_DOSE_AT = re.compile(r'@\s*' + _NUM, re.I)
_INPUT_WORDS = re.compile(
    r'\b(?:water|solution|dilut\w*|mix\w*|apply|applied|application|dissolv\w*|fertili[sz]\w*|urea|dap|potash|npk|manure|fym|'
    r'sulph?ur|zinc|gypsum|lime)\b', re.I)


def asks_for_dose(question):
    """The question wants an amount or schedule of a chemical ("how much monocrotophos per litre")."""
    q = question or ''
    return bool(_CHEM.search(q) and _QTY.search(q))


def pre_check(question, background=None):
    """Plain rules that run before any web search. Returns None to go on, or a finished result.

    no_dose    the question asks for a chemical dose: the web is not searched
    need_more  "How do I treat it?" with no diagnosed photo: ask which disease or pest
    off_topic  no farming word at all (and no diagnosed photo)
    """
    q = (question or '').strip()
    if not q or re.search(r'[ऀ-ॿ]', q):
        return None                      # text still in Hindi: leave it to the language model's own rules
    if asks_for_dose(q):
        return {'status': 'no_dose', 'answer': DOSE_MESSAGE, 'sources': []}
    if not background and not _FARM.search(q):
        if _PRONOUN.search(q):
            return {'status': 'need_more', 'answer': NEED_MORE, 'sources': []}
        return {'status': 'off_topic', 'answer': OFF_TOPIC, 'sources': []}
    return None


def has_dose(sentence):
    s = sentence or ''
    if _DOSE_AT.search(s) or _DOSE_SMALL.search(s):
        return True
    amount = _DOSE_PER.search(s) or _DOSE_RATE.search(s) or _DOSE_OF.search(s) or _DOSE_PPM.search(s) or _DOSE_PCT.search(s)
    return bool(amount and (_CHEM.search(s) or _INPUT_WORDS.search(s)))


def strip_doses(text):
    """Remove every sentence that gives an amount of a chemical, fertiliser or mix. Returns (text, sentences removed)."""
    out, removed = [], 0
    for line in (text or '').split('\n'):
        m = re.match(r'\s*(?:[-*•]|\d+[.)])\s+', line)
        lead = m.group(0) if m else ''
        parts = re.split(r'(?<=[.;!?])\s+', line[len(lead):].strip())
        kept = [p for p in parts if not has_dose(p)]
        removed += len(parts) - len(kept)
        kept = [p for p in kept if re.search(r'[A-Za-z]{3}', re.sub(r'\[[\d,\s]*\]', '', p))]
        if kept:
            out.append(lead + ' '.join(kept))
        elif not line.strip():
            out.append('')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip(), removed


def enough_left(text):
    """False when almost nothing is left after the doses were removed."""
    return len(re.sub(r'\[[\d,\s]*\]|[^A-Za-z]', '', text or '')) >= 40


# ---------------------------------------------------------------- gather + answer
def gather(question, search_q=None, timeout=None, max_pages=None, searcher=None, fetcher=None):
    """Returns (excerpts, status). status: ok | offline | none."""
    timeout = timeout or Config.WEB_TIMEOUT_SECONDS
    max_pages = max_pages or Config.WEB_MAX_PAGES
    q = search_q or search_query(question)
    if 'india' not in q.lower():
        q += ' India'                 # the farmers are in India: keeps other countries' schemes and rules out of the results
    errors, results = [], []
    try:
        results = (searcher or search_duckduckgo)(q, timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        logger.warning(f'Web search: no internet ({e.__class__.__name__})')
        return [], 'offline'
    except Exception as e:
        errors.append(f'DuckDuckGo: {e}')
    if not results:
        try:
            results = search_wikipedia(q, timeout)
        except (requests.ConnectionError, requests.Timeout):
            return [], 'offline'
        except Exception as e:
            errors.append(f'Wikipedia: {e}')
    if not results:
        logger.warning('Web search found nothing: ' + '; '.join(errors))
        return [], 'none'

    excerpts = []
    for r in _rank(results):
        if len(excerpts) >= max_pages:
            break
        text = r.get('text')
        if text:
            paras = [p.strip() for p in text.split('\n') if len(p.strip()) >= 50]
        else:
            try:
                paras = (fetcher or fetch_paragraphs)(r['url'], timeout)
            except Exception as e:
                logger.info(f'Web page skipped ({r["url"]}): {e}')
                paras = []
        body = best_excerpt(paras, question) if paras else ''
        if not body and r.get('snippet'):
            body = r['snippet']                         # at least the search snippet
        if len(body) < 80:
            continue
        excerpts.append({'n': len(excerpts) + 1, 'title': r['title'] or urlparse(r['url']).netloc, 'url': r['url'], 'text': body})
    return excerpts, ('ok' if excerpts else 'none')


def build_prompt(question, excerpts, background=None):
    blocks = '\n\n'.join(f'[{e["n"]}] {e["title"]} ({urlparse(e["url"]).netloc})\n{e["text"]}' for e in excerpts)
    bg = ''
    if background:
        bg = (f'\nBACKGROUND (about the farmer\'s photo; it is NOT part of the question):\n{background}\n'
              'Use it only if the question refers to "this", "it" or "my plant".\n')
    return f'''You are an agriculture assistant for cotton farmers in India.
Respond in English.

WEB EXCERPTS (found on the internet just now):
{blocks}
{bg}
QUESTION:
{question}

RULES:
1. Use only facts that appear in the WEB EXCERPTS. After each fact put the excerpt number in square brackets, like [1] or [2].
2. If the excerpts do not answer the question, reply exactly: {NO_ANSWER}
3. If the question is not about cotton, crops, plant health or farming, reply exactly: {OFF_TOPIC}
4. Never give an amount of any pesticide, chemical or fertiliser (no numbers with g, ml, kg, litre, per acre, per hectare, ppm) and never give a mixing ratio or spray schedule. You may name what to use only if the excerpts say so, with its [number], and without any amount.
5. No introduction and no commentary. At most 180 words. Use short bullet points ("- ") for steps or lists.

ANSWER:'''


def ask_ollama(prompt):
    r = requests.post(f'http://localhost:{Config.OLLAMA_PORT}/api/generate',
                      json={'model': Config.OLLAMA_MODEL, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.2}},
                      timeout=Config.OLLAMA_TIMEOUT)
    r.raise_for_status()
    return r.json().get('response', '').strip()


def _tidy(answer, excerpts):
    """Drop citation numbers that do not exist."""
    valid = {str(e['n']) for e in excerpts}

    def fix(m):
        nums = [n.strip() for n in m.group(1).split(',')]
        good = [n for n in nums if n in valid]
        return '[' + ', '.join(good) + ']' if good else ''
    return re.sub(r'\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]', fix, answer).strip()


def answer_from_web(question, background=None, search_q=None, searcher=None, fetcher=None, llm=None):
    """Returns {'status', 'answer', 'sources'}.

    status: ok          answer written from web pages; sources lists them
            off_topic   the question is not about cotton / farming (answer is the short refusal)
            no_dose     the question asks for a chemical dose, or the answer was only a dose (answer is a short refusal)
            need_more   the question points at "it" but no disease is known (answer asks which one)
            no_answer   pages were found but did not answer the question
            none        search found nothing usable
            offline     the internet could not be reached
            error       something else failed (see the log)
    """
    early = pre_check(question, background)
    if early:
        return early
    excerpts, status = gather(question, search_q=search_q, searcher=searcher, fetcher=fetcher)
    if status != 'ok':
        return {'status': status, 'answer': None, 'sources': []}
    try:
        text = (llm or ask_ollama)(build_prompt(question, excerpts, background))
    except Exception as e:
        logger.error(f'Web answer: the language model failed: {e}')
        return {'status': 'error', 'answer': None, 'sources': []}
    low = text.lower()
    if not text or low.startswith(NO_ANSWER.lower()[:30]) or 'could not find a reliable answer' in low:
        return {'status': 'no_answer', 'answer': None, 'sources': []}
    if low.startswith(OFF_TOPIC.lower()[:25]):
        return {'status': 'off_topic', 'answer': OFF_TOPIC, 'sources': []}
    answer, removed = strip_doses(_tidy(text, excerpts))
    if removed:
        if not enough_left(answer):
            return {'status': 'no_dose', 'answer': DOSE_MESSAGE, 'sources': []}
        answer += '\n' + DOSE_NOTE
    cited = set(re.findall(r'\[(\d+)\]', answer)) or {str(e['n']) for e in excerpts}
    sources = [{'n': e['n'], 'title': e['title'], 'url': e['url']} for e in excerpts if str(e['n']) in cited]
    return {'status': 'ok', 'answer': answer, 'sources': sources}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    question = sys.argv[1]
    print('Search words:', search_query(question))
    ex, st = gather(question)
    print('Status:', st)
    for e in ex:
        print(f'\n[{e["n"]}] {e["title"]}\n    {e["url"]}\n    {e["text"][:300]}...')
    if '--ask' in sys.argv and ex:
        print('\n--- answer ---')
        print(json.dumps(answer_from_web(question), indent=2, ensure_ascii=False))
