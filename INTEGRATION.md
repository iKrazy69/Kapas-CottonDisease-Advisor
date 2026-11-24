# Cotton disease + Voice RAG: what was added and how to run it

Photo of a cotton leaf -> cautious disease suggestion -> advice taken ONLY from the
documents you load, with sources -> follow-up questions (typed, or spoken in
Hindi/English via the existing voice endpoint).

## Run it (in this order)

1. **Install the extra packages** (inside your existing venv):
   `pip install -r backend/requirements.txt`
2. **Train the classifier** (once, needs your dataset folder):
   `python backend/cotton/train_classifier.py --data-dir "/path/to/Cotton Data set Man Mohan"`
   It prints test accuracy, per-class F1 and a confidence-threshold table, and
   writes `backend/cotton/models/cotton_svm.joblib` + `metrics.json`.
   Expect numbers close to the notebook's MSVM (about 73% accuracy, macro-F1 about 0.42);
   they will not match exactly (different library versions).
3. **Put real documents in `documents/`**: official cotton disease/pest guidance
   (ICAR, CICR, state agriculture departments, KVK bulletins). Without them the
   app says it has no official document and sends the farmer to a KVK/agriculture
   officer. It never makes up advice. PDFs need selectable text (no OCR).
4. **Set the two thresholds** in `backend/config.py` using step 2's printout:
   - `COTTON_MIN_PROBABILITY` (now 0.50, a placeholder): pick a row of the
     threshold table whose "accuracy when answered" you are willing to defend.
   - `MIN_COSINE_SIMILARITY` (now 0.30, placeholder): run `python evaluate_system.py`
     once cotton documents are loaded and pick a value between the in-scope and
     out-of-scope retrieval scores.
5. **Start**: `ollama serve` (with `llama3.1:8b`, `nomic-embed-text`), then
   `python backend/app.py` and open http://127.0.0.1:8080
6. **Test**: `python tests/test_cotton.py` (uses synthetic images and stubs; it
   checks the logic, not the model quality).

## New endpoints

- `POST /api/diagnose`  multipart: `image`, optional `language` (en|hi), `speak` (1)
  -> `diagnosis{status,disease,probability,top3,reasons,note}`, `advice`, `source_documents`,
  `grounded`, `session_id`, `audio_url`
- `POST /api/chat`  json: `question`, optional `session_id`, `language`, `speak`
- `GET /api/cotton-status`  what is loaded, languages, the model's real test metrics
- `GET /` (also `/diagnose`)  the Kapas site (frontend/index.html)
- `GET /legacy`  the earlier VB-GRAMG voice page (frontend/legacy-vbgramg.html)
- `GET /kapas.css`, `/kapas.js`, `/kapas-data.js`, `/chat-style.css`, `/fonts/<file>`  the site's own files

## Safety behaviour (by design)

- A result is "confident" only if its probability passes the threshold AND its
  class has test F1 >= `COTTON_MIN_CLASS_F1` (0.30). In the notebook's results three classes
  (Anthracnose, Boll rot, Root rot) score 0, so they will show as "Not sure" until the model improves.
- "Not sure" and "Healthy" never trigger treatment advice.
- Answers come from your loaded documents first (prompt rule in rag_engine.py). Only if the documents do not cover a question
  does the app look on the internet (see "Internet fallback" below). Chemical names and doses are only passed on if they appear
  in the document or web text, and web answers always carry the reminder to check with the KVK.
- Your question is passed on exactly as typed. The diagnosed disease is added only as separate background, and only when the
  question points at the photo ("it", "this", "my plant"); the answer says when it did.
- If translation fails the answer is shown in English and flagged, never silently mangled.

## Languages (honest status)

| Capability | Status |
|---|---|
| English, Hindi: typed question, answer, spoken answer | built; Hindi translation uses the local Llama, check it with a Hindi speaker |
| Hindi/English voice question | built (earlier fixes); Whisper small has about 38% word error rate on Hindi (published FLEURS figure) |
| Marathi, Gujarati, Telugu, Kannada, Tamil, ... typed | optional, OFF: set `ENABLE_INDICTRANS = True` in config.py and see `indic_translate.py` (UNTESTED here: gated models, extra installs) |
| Regional-language VOICE input | not supported: Whisper small is unusable on Gujarati (WER 106), Telugu (98), Kannada (100) |
| Regional-language spoken output | not built (Indic Parler-TTS is a possible later step; speed on your Mac unknown) |

## Internet fallback (backend/web_lookup.py)

When the loaded guides do not cover a question (or no guides are loaded), the app searches the web, downloads the top pages,
keeps the paragraphs that match, and has the local Llama answer only from them. The answer is labelled "From the internet, not your
loaded guides", numbered [1] [2] markers point to the pages, and the page links are shown so they can be opened and checked.

- Search: DuckDuckGo's plain page first, then Wikipedia. No account or key. Sources such as ICAR, CICR, KVK, .gov.in, .edu and FAO are
  tried first; social media and shops are skipped.
- Off-topic questions (not about cotton, crops or farming) are declined. If nothing reliable is found, or there is no internet,
  you get the "ask your KVK" message and a short note saying what happened.
- Turn it off with `ENABLE_WEB_LOOKUP = False` in config.py (the page then shows "Internet lookup off").
- Check it on your Mac (needs internet): `python backend/web_lookup.py "how does cotton leaf curl virus spread"`
  (add `--ask` to also run the Llama step). I could not reach the internet from where I built it, so the live search is NOT tested;
  the parsing and the logic are tested with stand-in pages in `python tests/test_web_lookup.py`.
- DuckDuckGo may refuse automated searches at times (the app then uses Wikipedia). For something sturdier, a search API with a key
  can be plugged in later.
- Web pages can be wrong or out of date, and this is not the same as the loaded official guides. Say so in the report.

## Evaluation kit (eval/)

`eval/README.md` has the run order. It measures whether the system is safe, not just that it runs:
the classifier's abstention behaviour with confidence intervals (`abstention_study.py`), grounded versus ungrounded answers on a
50-question English/Hindi set tied to guide lines (`advisor_benchmark.py`, `cotton_qa_benchmark.json`), and whether doses survive
loading (`kb_audit.py`). The question set is a DRAFT: written from the guide, not checked by a cotton expert or a Hindi speaker.

**Document loader fix (important).** The old loader deleted `%`, `@`, `/` and range dashes from every document before storing it
("@ 25-30 g" became "2530 g", "1-5%" became "15"). `backend/document_processor.py` now keeps them. Documents already in the database were
stored with the old loader: stop the app, run `mv chroma_data chroma_data_before_cleaning_fix`, then `python eval/reload_knowledge_base.py`
(Ollama running); it re-loads the documents and checks the doses. Until then the advisor can quote garbled doses.

## The site (frontend/index.html, kapas.css, kapas.js, kapas-data.js, fonts/)

Rebuilt on 23 Nov 2026. The photo check and the guide chat are the first section; below them are sections on how it works, cotton (facts), the season/risk tables, the history of cotton, and an entry for each of the 14 diseases in the guide. Selecting a disease in the list or in the season table scrolls to its entry; an entry has an "Ask Kapas" button that sends a question to the chat. The page calls the same endpoints as before (`/api/cotton-status`, `/api/diagnose`, `/api/chat`, and `/api/voice-query` for the microphone button), so the safety rules are untouched. The disease entries are written from the guide text and carry no spray names or doses on purpose; doses come only from the chat, which reads them from the guide and names the page. The old single-file photo page is kept in `_pre_final_backup/frontend/`.

The picture beside the headline is a drawn cotton plant (frontend/index.html, drawn as SVG; it is decoration and is hidden from screen readers). It grows and opens its bolls on load, sways, flutters when the pointer brushes it, and can be touched: a closed boll opens, an open boll puffs out lint seeds, and the flower turns from cream to pink. With "reduce motion" switched on in the computer it appears already grown and does not move. The Hindi word in the header uses the computer's own Devanagari font (none is bundled), so its look depends on the device.

No internet needed (the two fonts, Gloock and Instrument Sans, are in frontend/fonts under the SIL Open Font Licence; no CDNs or tracking). It has English and Hindi screen text, light and dark themes
(follows the computer's setting; the round button switches it), and works on a phone. It only changes how things look; the
endpoints and safety rules above are untouched.

- The result shows the model score as a gauge with the server's minimum (`COTTON_MIN_PROBABILITY`) marked on it, the three closest guesses,
  and the test score for that disease. "Not sure" never shows a disease name as the verdict and never gives spray advice.
- Spoken answers are cleaned first (`backend/speech_text.py`): markdown marks, "(Source 1)", file names, links and symbols are removed, "%" is said as "percent", and the text is split at commas and full stops so a short silence is played there instead of the mark being read out. If your Piper version rejects this, it falls back to one pass over the same cleaned text. Run `python tests/test_speech_text.py` to check it. Not heard on real speakers by me, so listen once in English and once in Hindi.
- Photos over 1600 px are shrunk in the browser before upload (the server refuses files over 10 MB).
- The "What Kapas can and cannot recognise" panel is read from `metrics.json`, so it updates itself after you retrain.
- Disease names stay in English (the model's class names); only the screen text and the answers are translated.
- Not verified: the Hindi screen text has not been checked by a native speaker. Have a Hindi speaker read it before the demo.
- Tested in Chromium (Playwright) with mocked API replies in the real response shapes, at desktop and phone sizes, light and dark, with reduced motion on, and once served by the real Flask app (routes, fonts and files load, no console errors). Not tested with a live Ollama backend, a real microphone, real Piper audio, or a real iPhone or Android camera: open the site once on the demo computer and try each of those.
- The Hindi strings added for the new sections and the microphone button are not checked by a native speaker. The history and cotton facts come from the CICR guide introduction and public sources; the sources are listed in the page footer.

## Not done / not verified

- Other crops: nothing built. The flow is crop-agnostic (`cotton_flow.disease_query`), but there is no second classifier.
- Not run on your Mac: the Mac-side packages (opencv, scikit-image, scikit-learn) were not installed by me.
- The classifier's accuracy on real field photos is unknown; the dataset is small and imbalanced (see metrics.json).
- Dataset provenance still has to be filled in for your report.
- Boll rot and Root rot: the two folders hold the same 35 photos under two labels (`eval/results/dataset_duplicates.md`). Both classes are dropped from the model until someone who knows cotton decides what the photos show.
- The benchmark questions, their answer keys and the Hindi wording are drafts (see the evaluation kit); no expert has checked them.
- The guide contradicts itself on some bacterial blight doses (eval/README.md, item 2); the advisor can quote either value.
