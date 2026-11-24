"""
Calibrate the "is the question covered by the guide at all" cutoff (Config.MIN_COSINE_SIMILARITY).

The app asks the document search for the best passage and refuses to use the documents when the best similarity is below
the cutoff. The cutoff was a placeholder (0.30) and never fired: even "What is the capital of France?" scored 0.52.

How the cutoff is chosen (decided before looking at the held-out questions):
  1. Development scores: the best similarity of every benchmark question, taken from the saved benchmark runs
     (condition "rag"). Questions the guide can answer are in_document, followup and conflict; off-topic questions are out_of_scope.
  2. If the lowest "answerable" score is at least 0.04 above the highest "off-topic" score, the cutoff is the midpoint,
     rounded to two decimals. If not, there is no clean cutoff and 0.30 stays.
  3. Held-out check: 24 new farmer-style questions the guide answers and 12 off-topic questions that are NOT in the
     benchmark are scored with the real search. The cutoff is adopted only if every held-out answerable question scores at
     or above it and every held-out off-topic question scores below it.
Cotton questions the guide does NOT cover (prices, insurance, ...) score as high as covered ones, so a similarity cutoff
cannot catch them; they are reported, not used for the rule. The model's own refusal and the internet-fallback rules handle them.

    python eval/calibrate_retrieval_cutoff.py --runs eval/results/final_run_1.jsonl
    python eval/calibrate_retrieval_cutoff.py --dev-only        (no Ollama: development scores only)

Needs Ollama running (it embeds the questions) and the guide loaded. No language model answers anything here.
Writes eval/results/cutoff_calibration.json and .md. It never edits config.py by itself.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import advisor_benchmark as AD  # noqa: E402

HELD_OUT_ANSWERABLE = [
    'How do I control thrips in my cotton field?',
    'What does pink bollworm damage look like?',
    'How many pheromone traps should I install for pink bollworm?',
    'How do I manage aphids on cotton?',
    'What is Target spot of cotton and how do I recognise it?',
    'How can I manage grey mildew in cotton?',
    'What are the symptoms of Fusarium wilt in cotton?',
    'How can I control mealybugs in cotton?',
    'How does neem help against sucking pests in cotton?',
    'What are the symptoms of Alternaria leaf spot?',
    'How do I manage root-knot nematodes in cotton?',
    'What is Verticillium wilt?',
    'How do jassids damage cotton?',
    'What are mirid bugs and how do I manage them?',
    'How do yellow sticky traps help against whitefly?',
    'How should I dispose of crop residue to reduce disease?',
    'How does weather affect boll rot?',
    'Which weeds should I remove to reduce leaf curl virus?',
    'What is the role of Trichoderma in cotton disease management?',
    'How can I recognise cotton leaf curl disease in the field?',
    'How can I tell if my cotton has bacterial blight?',
    'What is the Per Cent Disease Index?',
    'How do I manage dusky cotton bug?',
    'How do I use pheromone traps to monitor bollworm?',
]
HELD_OUT_OFF_TOPIC = [
    'Who is the prime minister of India?',
    'What is the weather today in Delhi?',
    'How do I reset my phone password?',
    'What is a good recipe for paneer?',
    'Translate hello into French.',
    'When is the next cricket match?',
    'How do I lose weight fast?',
    'What is the price of gold today?',
    'Write a poem about the moon.',
    'How do I apply for a driving licence?',
    'Which laptop should I buy?',
    'Explain how aeroplanes fly.',
]
HELD_OUT_COTTON_NOT_COVERED = [   # reported only
    'What price will the government pay for my cotton?',
    'How do I get a loan for my cotton farm?',
    'Which cotton variety gives the highest yield?',
    'What subsidy is there for buying a tractor?',
    'What is the cotton market price today?',
    'What are the rules for exporting cotton?',
]
MARGIN = 0.04
DEFAULT_CUTOFF = 0.30
ANSWERABLE = ('in_document', 'followup', 'conflict')


def dev_scores(run_paths, items):
    by_id = {i['id']: i for i in items}
    out = {'answerable': [], 'off_topic': [], 'cotton_not_covered': []}
    seen = set()
    for path in run_paths:
        for r in AD.load_records(path):
            if r.get('condition') != 'rag' or 'error' in r or r.get('retrieval_score') is None or r['id'] not in by_id:
                continue
            cat = by_id[r['id']]['category']
            key = (path, r['id'], r['lang'])
            if key in seen:
                continue
            seen.add(key)
            row = (round(float(r['retrieval_score']), 4), r['id'], r['lang'])
            if cat in ANSWERABLE:
                out['answerable'].append(row)
            elif cat == 'out_of_scope':
                out['off_topic'].append(row)
            elif cat == 'not_in_guide':
                out['cotton_not_covered'].append(row)
    return out


def choose_cutoff(dev):
    """Midpoint of the gap between the lowest answerable score and the highest off-topic score, if the gap is clean."""
    if not dev['answerable'] or not dev['off_topic']:
        return None, 'not enough development scores'
    lo_in = min(s for s, _, _ in dev['answerable'])
    hi_out = max(s for s, _, _ in dev['off_topic'])
    if lo_in - hi_out < MARGIN:
        return None, f'no clean gap: lowest answerable {lo_in:.3f}, highest off-topic {hi_out:.3f} (needs a gap of {MARGIN})'
    return round((lo_in + hi_out) / 2, 2), f'gap {hi_out:.3f} to {lo_in:.3f}'


def validate(cutoff, held):
    """held = {'answerable': [(score, question)], 'off_topic': [...]}. Returns (ok, wrongly_blocked, wrongly_kept)."""
    blocked = [(s, q) for s, q in held['answerable'] if s < cutoff]
    kept = [(s, q) for s, q in held['off_topic'] if s >= cutoff]
    return (not blocked and not kept), blocked, kept


def decide(dev, held):
    """The whole rule in one place (also used by the tests). Returns a dict with 'adopt', 'cutoff', 'reason'."""
    cutoff, why = choose_cutoff(dev)
    if cutoff is None:
        return {'adopt': False, 'cutoff': DEFAULT_CUTOFF, 'reason': why}
    if held is None:
        return {'adopt': False, 'cutoff': DEFAULT_CUTOFF, 'candidate': cutoff, 'reason': f'candidate {cutoff} ({why}) not validated on held-out questions'}
    ok, blocked, kept = validate(cutoff, held)
    if ok:
        return {'adopt': True, 'cutoff': cutoff, 'reason': f'{why}; every held-out answerable question scored at or above it and every held-out off-topic question below it'}
    return {'adopt': False, 'cutoff': DEFAULT_CUTOFF, 'candidate': cutoff,
            'reason': f'candidate {cutoff} ({why}) failed the held-out check: {len(blocked)} answerable question(s) below it, {len(kept)} off-topic question(s) at or above it'}


def held_out_scores(top_k=5):
    sys.path.insert(0, os.path.join(ROOT, 'backend'))
    from rag_engine import RAGEngine
    rag = RAGEngine()
    if not rag.has_documents():
        raise SystemExit('No documents are loaded. Run:  python eval/reload_knowledge_base.py')

    def best(q):
        _, _, sims = rag._retrieve_context(q, top_k)
        sims = [s for s in sims if s > 0.0]   # keyword-rescued passages carry 0.0 and are not search scores
        return round(float(max(sims)), 4) if sims else 0.0
    return {k: [(best(q), q) for q in qs] for k, qs in
            (('answerable', HELD_OUT_ANSWERABLE), ('off_topic', HELD_OUT_OFF_TOPIC), ('cotton_not_covered', HELD_OUT_COTTON_NOT_COVERED))}


def render(dev, held, result):
    def rng(rows):
        return f'{min(s for s, *_ in rows):.3f} to {max(s for s, *_ in rows):.3f} (n = {len(rows)})' if rows else '-'
    L = ['# Retrieval cutoff calibration', '',
         f'Current cutoff in config.py: {DEFAULT_CUTOFF}. Decision: **{"ADOPT " + str(result["cutoff"]) if result["adopt"] else "KEEP " + str(DEFAULT_CUTOFF)}**. {result["reason"]}.', '',
         '| group | best-passage similarity range |', '|---|---|',
         f'| development, guide answers it (benchmark, en + hi) | {rng(dev["answerable"])} |',
         f'| development, off-topic (benchmark, en + hi) | {rng(dev["off_topic"])} |',
         f'| development, cotton but not in the guide (benchmark, en + hi) | {rng(dev["cotton_not_covered"])} |']
    if held:
        L += [f'| held-out, guide answers it | {rng(held["answerable"])} |', f'| held-out, off-topic | {rng(held["off_topic"])} |',
              f'| held-out, cotton but not in the guide | {rng(held["cotton_not_covered"])} |']
    L += ['', 'Cotton questions the guide does not cover score as high as covered ones, so a similarity cutoff cannot catch them. '
              'The model\'s refusal and the internet-fallback rules handle those.', '',
          'Held-out questions are drafts written for this check and in English only; the Hindi questions reach the search as English translations.']
    if held:
        for name in ('answerable', 'off_topic', 'cotton_not_covered'):
            L += ['', f'### held-out: {name}', ''] + [f'- {s:.3f}  {q}' for s, q in sorted(held[name])]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', nargs='*', default=[os.path.join(AD.RESULTS, 'advisor_run.jsonl')])
    ap.add_argument('--dev-only', action='store_true', help='only the development scores from the saved runs (no Ollama)')
    ap.add_argument('--out-dir', default=AD.RESULTS)
    a = ap.parse_args()
    items = AD.load_items()
    dev = dev_scores(a.runs, items)
    held = None if a.dev_only else held_out_scores()
    result = decide(dev, held)
    text = render(dev, held, result)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, 'cutoff_calibration.md'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    with open(os.path.join(a.out_dir, 'cutoff_calibration.json'), 'w', encoding='utf-8') as fh:
        json.dump({'result': result, 'dev': dev, 'held_out': held}, fh, indent=1)
    print(text)
    print(('ADOPT %s' if result['adopt'] else 'KEEP %s') % result['cutoff'])


if __name__ == '__main__':
    main()
