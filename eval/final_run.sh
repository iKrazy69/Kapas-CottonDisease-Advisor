#!/bin/bash
# One command that finishes the measurements for the thesis:
#
#     bash eval/final_run.sh
#
# It takes about 2 to 3 hours. Keep the Mac plugged in; the script keeps it awake while it runs.
# It is safe to stop (Ctrl+C) and start again: finished answers are kept and only the missing ones are asked.
#
# What it does:
#   1. checks that Ollama is running and has the two models
#   2. runs all the unit tests (a few minutes at most) and tells you which, if any, fail
#   3. checks the guide search with no language model (seconds) and compares it with the earlier measurement
#   4. calibrates the retrieval cutoff (benchmark scores from the earlier run + 36 new held-out questions);
#      it changes backend/config.py only if the held-out check passes, and keeps a backup
#   5. three full runs of the benchmark (50 questions x 3 systems x English/Hindi), same settings, temperature 0
#   6. report and blind rating sheet from run 1, and the ranges over the 3 runs, in eval/results/final/
#      (the old report and the old rating sheet in eval/results/ are never touched)
#
# Everything is written to eval/results/final/. The log is eval/results/final/final_run.log.

set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p eval/results/final _pre_final_backup/backend
exec > >(tee -a eval/results/final/final_run.log) 2>&1

echo "=== final run started $(date '+%Y-%m-%d %H:%M:%S') ==="

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i -w $$ &
fi

if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -f venv/bin/activate ]; then
    source venv/bin/activate
  else
    echo "No virtual environment found (venv/). Activate yours and run again."; exit 1
  fi
fi

echo "--- 1. Ollama"
TAGS=$(curl -s -m 8 http://localhost:11434/api/tags || true)
if [ -z "$TAGS" ]; then
  echo "Ollama is not running. Start it (open the Ollama app, or run: ollama serve) and run this again."; exit 1
fi
echo "$TAGS" | grep -q "llama3.1" || { echo "The model llama3.1:8b is missing. Run: ollama pull llama3.1:8b"; exit 1; }
echo "$TAGS" | grep -q "nomic-embed-text" || { echo "The model nomic-embed-text is missing. Run: ollama pull nomic-embed-text"; exit 1; }
echo "Ollama is running with both models."

echo "--- 2. unit tests"
FAILED_TESTS=""
for t in tests/test_*.py; do
  if python "$t" > /tmp/test_out.txt 2>&1; then
    echo "ok    $t"
  else
    echo "FAILED $t"; tail -5 /tmp/test_out.txt; FAILED_TESTS="$FAILED_TESTS $t"
  fi
done
if [ -n "$FAILED_TESTS" ]; then
  echo "Some tests failed:$FAILED_TESTS . Stopping so that no hours are spent on a broken build. See the log above."; exit 1
fi

echo "--- 3. guide search check (no language model)"
python eval/retrieval_check.py --label final --compare rebuilt || echo "(search check failed; continuing)"

echo "--- 4. retrieval cutoff"
if [ ! -f eval/results/cutoff_calibration.json ]; then
  python eval/calibrate_retrieval_cutoff.py --runs eval/results/advisor_run.jsonl || echo "(calibration failed; the cutoff stays as it is)"
else
  echo "Already calibrated (eval/results/cutoff_calibration.json). Delete that file to calibrate again."
fi
python - <<'PY'
import json, os, re, shutil
p = 'eval/results/cutoff_calibration.json'
if not os.path.exists(p):
    raise SystemExit
res = json.load(open(p))['result']
cfg = 'backend/config.py'
src = open(cfg, encoding='utf-8').read()
m = re.search(r'MIN_COSINE_SIMILARITY = ([0-9.]+)', src)
now = float(m.group(1)) if m else None
if res.get('adopt') and now is not None and abs(now - res['cutoff']) > 1e-9:
    shutil.copy2(cfg, '_pre_final_backup/backend/config.before_cutoff.py')
    open(cfg, 'w', encoding='utf-8').write(re.sub(r'MIN_COSINE_SIMILARITY = [0-9.]+', f"MIN_COSINE_SIMILARITY = {res['cutoff']}", src, count=1))
    print(f"Cutoff changed from {now} to {res['cutoff']} in backend/config.py (backup: _pre_final_backup/backend/config.before_cutoff.py).")
else:
    print(f"Cutoff stays {now}. Reason: {res.get('reason')}")
PY

echo "--- 5. benchmark runs"
for n in 1 2 3; do
  echo "=== run $n of 3 ($(date '+%H:%M')) ==="
  for attempt in 1 2; do
    python eval/advisor_benchmark.py run --models llama3.1:8b --langs en,hi --temperature 0 --out eval/results/final_run_$n.jsonl \
      || echo "(run $n stopped with an error; trying the missing answers again)"
  done
done

echo "--- 6. report, rating sheet, ranges"
COMPLETE=$(python - <<'PY'
import sys
sys.path.insert(0, 'eval')
import advisor_benchmark as AD
items = AD.load_items()
need = len(items) * len(AD.CONDITIONS) * 2
have = len([r for r in AD.load_records('eval/results/final_run_1.jsonl') if 'error' not in r])
print('yes' if have >= need else f'no ({have} of {need})')
PY
)
echo "Run 1 complete: $COMPLETE"
if [ -f eval/results/final/rating_sheet.csv ]; then
  echo "eval/results/final/rating_sheet.csv already exists: NOT rewriting it (people may already be rating it)."
elif [ "$COMPLETE" = "yes" ]; then
  python eval/advisor_benchmark.py report --runs eval/results/final_run_1.jsonl --out-dir eval/results/final > /dev/null
  cp eval/results/final/rating_sheet.csv eval/results/final/rating_sheet.ORIGINAL.csv
  cp eval/results/final/rating_key.csv eval/results/final/rating_key.ORIGINAL.csv
  echo "Blind rating sheet written to eval/results/final/rating_sheet.csv (copies: *.ORIGINAL.csv)."
else
  echo "Run 1 is not complete, so the rating sheet is not written yet. Run this script again."
fi
python eval/final_ranges.py --runs eval/results/final_run_1.jsonl eval/results/final_run_2.jsonl eval/results/final_run_3.jsonl --out-dir eval/results/final | head -60

echo "=== final run finished $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Done. Everything is in eval/results/final/."
