"""
Places where the loaded guide gives two different amounts for the same product on the same disease.

Why this exists: a farmer who asks "how much per 10 litres?" must not be handed one of two numbers as if it were
the only one. The guide (ICAR-CICR 2026) says 30 g per 10 L for one spray in its crop-stage advice and 25 g per
10 L for the same spray in its summary table. The language model usually shows one of them. This module adds a
fixed note that shows both and says the guide disagrees with itself.

How it works (no language model involved, so it is the same every time):
  - CONFLICTS is a short list found by scanning the whole guide for the same product, strength and unit with
    different amounts (eval/find_dose_conflicts.py) and checking each one by hand against the guide text.
  - note_for() adds the note only when (a) the question (or the diagnosed disease) is about that disease,
    (b) the retrieved passages contain one of the amounts, and (c) the answer shows one of the amounts or the
    question asks "how much", and (d) the answer does not already show all of them.
  - Every amount in CONFLICTS is checked against the guide text by tests/test_dose_conflicts.py.

Limits: only the conflicts in the list are handled. Other repeated products in the guide differ for good reasons
(different pest or crop stage); they are not touched. The list is not a proof that the guide has no other conflict.
"""
import re

# What counts as asking for an amount (the question has already been translated to English by the app).
_ASKS_AMOUNT = re.compile(
    r"\bhow\s+much\b|\bdose\b|\bdosage\b|\bamount\b|\bquantity\b|\bhow\s+many\s+(?:g|gram|grams|ml|kg)\b|"
    r"\bper\s+(?:\d+\s*)?(?:l|litre|litres|liter|liters|kg|acre|hectare|ha)\b|\bmix(?:ing|ture)?\b|\bconcentration\b|"
    r"\bwhat\s+spray\b|\bwhich\s+(?:spray|fungicide)\b|\bspray\s+schedule\b", re.I)

CONFLICTS = [
    {
        'id': 'blb_foliar_spray',
        'about': 'bacterial leaf blight, foliar spray',
        'when': r'bacterial\s+(?:leaf\s+)?blight|\bblb\b',
        'product': 'Carbendazim 12% + Mancozeb 63% WP',
        'variants': [
            {'dose': '30 g per 10 L of water', 'where': 'the crop-stage advice',
             'seen': r'carbendazim\s*12\s*%?\s*\+\s*mancozeb\s*63\s*%?\s*wp\s*@?\s*30\s*g\s*/?\s*(?:per\s*)?10\s*l',
             'said': r'(?<![\d.])30\s*g\s*/\s*10\s*l'},
            {'dose': '25 g per 10 L of water', 'where': 'the summary table',
             'seen': r'carbendazim\s*12\s*%?\s*\+\s*mancozeb\s*63\s*%?\s*wp\s*@?\s*25\s*g\s*/?\s*(?:per\s*)?10\s*l',
             'said': r'(?<![\d.])25\s*g\s*/\s*10\s*l'},
        ],
    },
    {
        'id': 'blb_seed_treatment',
        'about': 'bacterial leaf blight, seed treatment',
        'when': r'bacterial\s+(?:leaf\s+)?blight|\bblb\b',
        'product': 'Carboxin 37.5% + Thiram 37.5%',
        'variants': [
            {'dose': '3.5 g per kg of seed', 'where': 'the crop-stage advice',
             'seen': r'carboxin\s*37\.5\s*%?\s*\+\s*thiram\s*37\.5\s*%?\s*(?:ws|ds)\s*@?\s*3\.5\s*g\s*/\s*kg',
             'said': r'(?<![\d.])3\.5\s*g\s*/\s*kg'},
            {'dose': '2.5 g per kg of seed', 'where': 'the summary table',
             'seen': r'carboxin\s*37\.5\s*%?\s*\+\s*thiram\s*37\.5\s*%?\s*(?:ws|ds)\s*@?\s*2\.5\s*g\s*/\s*kg',
             'said': r'(?<![\d.])2\.5\s*g\s*/\s*kg'},
        ],
    },
    {
        'id': 'boll_rot_carbendazim',
        'about': 'boll rot spray',
        'when': r'boll\s*rot',
        'product': 'Carbendazim 50% WP',
        'variants': [
            {'dose': '1 g per L of water', 'where': 'the summary table',
             'seen': r'boll\s*rot[^.]{0,40}spray\s+carbendazim\s*50\s*%?\s*wp\s*@?\s*1\s*g\s*/\s*l',
             'said': r'(?<![\d.])1\s*g\s*/\s*(?:1\s*)?l(?![\w])'},
            {'dose': '4 g per 10 L of water', 'where': 'the crop-stage advice (its list of sprays is given per 10 litres of water)',
             'seen': r'carbendazim\s*50\s*%?\s*wp\s*@\s*4\s*g\s+followed\s+by',
             'said': r'(?<![\d.])4\s*g\b(?!\s*/\s*kg)'},
        ],
    },
]

NOTE_TEMPLATE = ('Note: the guide gives different amounts for this. {parts} '
                 'The guide does not say which one is right, so please check the product label or ask your KVK before spraying.')


def _flat(text):
    """Lower case, single spaces, litres written as l, "per" written as a slash (for answers)."""
    t = re.sub(r'\s+', ' ', (text or '').lower())
    t = re.sub(r'\b(?:litres|litre|liters|liter)\b', 'l', t)
    t = re.sub(r'\b(?:grams|gram)\b', 'g', t)
    t = re.sub(r'\bper\b', '/', t)
    t = re.sub(r'\s*/\s*', '/', t)
    return t


def _raw_flat(text):
    return re.sub(r'\s+', ' ', (text or '').lower())


def asks_for_amount(question):
    return bool(_ASKS_AMOUNT.search(question or ''))


def note_for(question, answer, chunks, topic_extra=''):
    """Return the note to append to a grounded answer, or '' when none is needed.

    question     the farmer's question in English
    answer       the model's answer
    chunks       the passages the answer was based on
    topic_extra  other text that says what the question is about (the search words, the diagnosed disease)
    """
    ctx = _raw_flat(' '.join(chunks or []))
    topic = _raw_flat((question or '') + ' ' + (topic_extra or ''))
    ans = _flat(answer)
    parts = []
    for c in CONFLICTS:
        if not re.search(c['when'], topic):
            continue
        if not any(re.search(v['seen'], ctx) for v in c['variants']):
            continue
        said = [v for v in c['variants'] if re.search(v['said'], ans)]
        if not said and not asks_for_amount(question):
            continue
        if len(said) == len(c['variants']):
            continue
        parts.append(f"{c['product']} ({c['about']}): " +
                     ' and '.join(f"{v['dose']} in {v['where']}" for v in c['variants']) + '.')
    return NOTE_TEMPLATE.format(parts=' '.join(parts)) if parts else ''
