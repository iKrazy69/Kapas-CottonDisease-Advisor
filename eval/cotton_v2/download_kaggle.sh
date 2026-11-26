set -u
OUT="$HOME/Downloads/Cottondataset/v2/raw"
mkdir -p "$OUT"
for ref in "$@"; do
  name=$(echo "$ref" | tr '/' '__')
  if [ -f "$OUT/$name.zip.done" ]; then echo "skip $ref"; continue; fi
  echo "start $ref $(date +%T)"
  curl -sL --retry 3 -C - -o "$OUT/$name.zip" "https://www.kaggle.com/api/v1/datasets/download/$ref" && unzip -tq "$OUT/$name.zip" >/dev/null && touch "$OUT/$name.zip.done" && echo "done $ref $(du -h "$OUT/$name.zip" | cut -f1) $(date +%T)" || echo "FAIL $ref"
done
