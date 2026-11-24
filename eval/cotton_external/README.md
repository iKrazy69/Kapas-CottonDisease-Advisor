# Outside-photo tests for the cotton classifier

Question: the saved classifier scores 80.2% on its own 81 test photos. Does that hold on photos from other sources, and when should the app stay silent?

Run on 22 Nov 2026 with photos from four public datasets plus the project's own photos. The live model was not changed.

## What came out

| Check | Result |
|---|---|
| This pipeline vs the saved model | Same 368 training / 81 test photos, 80.25% accuracy, identical cutoff table. Everything below uses this pipeline. |
| Twin photos inside the project's own set | 13 of the 81 test photos have a near-identical twin in training (same leaf photographed twice): all 13 right. The other 68: 76.5% right. Grouped 5-fold cross-validation 76.9%, random 5-fold 78.1%. So the 80% is a little flattering, not badly so. |
| Bacterial blight on outside photos | East West 80.8% top-1 (n=182), SAR-CLD 83.2% (n=137, augmented), Severity 53.8% (n=119), Ayaz validation 35.9% (n=39). Own photos: 95.5% (n=44). |
| Healthy leaves on outside photos | Named healthy only 1.2% (East West, n=172), 2.3% (SAR-CLD, n=131), 8.0% (Severity, n=789), 7.7% (Ayaz validation, n=39). 22-45% of them are called a disease *confidently*. |
| Curl virus on outside photos | 40% (Severity, n=20), 14% (SAR-CLD, n=136, augmented). |
| Conditions the model never saw | All 21 groups pooled: a confident wrong answer for 42.8% (41-45%) of 2,167 photos (927). Per group 18-79% (Fusarium wilt on East West 79%, Alternaria 73%, leaf reddening 57%). The project's own Boll/Root rot photos: 31% (n=35). |
| Photo size | Not the cause: shrinking the project's own test photos to 400 px changes 3 of 81 answers (80.2% -> 77.8%). |
| Dataset fingerprint | A model that sees only the 31 numbers recognises which dataset a photo came from 77.8% of the time (chance 20%). The features partly read camera and background. |
| Cutoff 0.70 | Chosen on the test photos originally. On the 80 validation photos it gives 96.0% right (answers 50/80), on test 90.4%. A cutoff picked by rule on validation (0.46) gives only 82.7% on test: with 80 photos the choice is unstable, 0.70 stays. |
| Retrained candidate (several datasets, 13 classes) | Better on datasets it trained on, not on a new one: leave-one-dataset-out accuracy 57% (East West), 41% (Ayaz), 45% (own, n=64), 13% (Severity). Worse than the live model on the project's own photos (66.7% vs 80.2%). **Not adopted.** Saved separately as `eval/results/cotton_external/candidate/` (trained with scikit-learn 1.9.1; the venv has 1.3.2, so re-run `candidate_study.py --save-dir` there if you want to load it). |
| "Unfamiliar photo" check (distance to training photos) | Separates own test photos from outside photos with AUROC 0.853. With it, confident wrong answers on never-seen photos fall from 42.8% to 26.8%, but 56% of outside photos still look familiar enough to be answered (580 of 2,167 never-seen photos still get a confident wrong answer). **Not adopted.** |

Plain reading: the classifier works for leaf photos like the training photos (single leaf, plain light background, the same camera setup) and not for anything else. It cannot tell the app when a photo is of a different kind. For the thesis this is the main finding: the cutoff rule stays silent on about a third of the project's own photos (it answers 52 of 81) but does not reliably stay silent on photos from other places.

## Files

| File | Job |
|---|---|
| `prep_images.py` | Reads photos from zips/folders (read-only), writes 224x224 PNG copies and `manifest.csv` (md5, size, class). Needs only numpy and OpenCV. Resumable. `--pre-shrink N` is the resolution experiment. |
| `extract_features.py` | The classifier's 31 features for every PNG -> `features.csv`. Needs scikit-image (the app's own `backend/cotton/features.py`). |
| `dup_check.py` | Exact (same bytes) and near-identical (flip/rotation-proof 16x16 hash) photos -> `near_pairs.csv`, `nn.csv`. |
| `reproduce_split.py` | **Run first.** Rebuilds the saved model's split, checks 80.25%, writes `own614_split.json`. |
| `external_test.py` | Live model on every outside photo: shared classes and never-seen conditions. |
| `internal_check.py` | Twin photos in the own set, random vs grouped cross-validation, dataset fingerprint. |
| `resolution_test.py` | Own photos shrunk before the 224 resize. |
| `threshold_validation.py` | Cutoff chosen on validation photos, checked on test and outside photos. |
| `candidate_study.py` | The retrain study (does not touch `backend/`). |
| `ood_gate.py` | The "unfamiliar photo" check. |
| `common.py` | Shared helpers (class names, intervals, cleaning rules). |
| `DATASETS.md` | Dataset table for the thesis (sources, licences, counts, what we found). |
| `../../tests/test_cotton_external.py` | Tests for the helpers. |
| `../results/cotton_external/` | Output of the 22 Nov run (small files; the 224x224 PNGs stay in `Cottondataset/_work/`). |

## Run it again

Needs the photos (project's two Drive zips in Downloads, the dataset folders in `Downloads/Cottondataset`), and in the venv: numpy, OpenCV, scikit-image, scikit-learn, scipy, joblib (already there) plus `pandas` (`pip install pandas`).

```
cd Kapas-CottonDisease-Advisor
source venv/bin/activate
pip install pandas
python eval/cotton_external/prep_images.py --downloads ~/Downloads --data ~/Downloads/Cottondataset --out ~/Downloads/Cottondataset/_work
python eval/cotton_external/extract_features.py --work ~/Downloads/Cottondataset/_work
python eval/cotton_external/dup_check.py --work ~/Downloads/Cottondataset/_work
python eval/cotton_external/reproduce_split.py --work ~/Downloads/Cottondataset/_work --model backend/cotton/models/cotton_svm.joblib --metrics backend/cotton/models/metrics.json
python eval/cotton_external/external_test.py --work ~/Downloads/Cottondataset/_work --model backend/cotton/models/cotton_svm.joblib --metrics backend/cotton/models/metrics.json
```

The other scripts take the same `--work/--model/--metrics`. `resolution_test.py` also needs `prep_images.py --only own614 --pre-shrink 1000` and `--pre-shrink 400` run with `--out ~/Downloads/Cottondataset/_work/shrink_1000` and `.../shrink_400`, then `extract_features.py --work` on each. `prep_images.py` was run in a Linux sandbox on 22 Nov (OpenCV 5.0.0) and the features in a second sandbox; the saved model's numbers matched exactly, so OpenCV versions did not matter here.

## Read before quoting numbers

- Labels come from the dataset authors' papers/pages; no cotton expert has checked them. East West has 25 pairs of identical photos filed under two different diseases, and the project's "Boll rot" and "Root rot" folders hold the same 35 photos.
- "Never seen" means never seen by this classifier. The CICR guide may cover these diseases.
- SAR-CLD was only available as augmented copies (flips, rotations, brightness). It is used for the never-seen test and shown separately for shared classes, never in a headline accuracy. Its effective number of different photos is smaller than the count.
- Photos were cleaned before scoring: files whose bytes appear under two labels in one dataset are dropped, exact copies are collapsed to one, and photos within 4 bits of an earlier photo of the same class and dataset are collapsed (counts per dataset in `eval/results/cotton_external/external_results.json`).
- The Ayaz sets were sampled (150 per class from Training Data; all of Validation-Testing). Ayaz Training and Validation-Testing overlap: 40 exact pairs and 449 near pairs in the sample.
- In `candidate_study.py` the 20% test portions of East West, Severity and Ayaz come from datasets the candidate trained on, so they are not outside tests; SAR-CLD and leave-one-dataset-out are.
- One run, one seed, one classifier recipe. Differences of a few points between rows are not reliable (intervals are Wilson 95%).
- Only tested with pandas 3 and numpy 2.5 in the sandbox. The Mac venv has numpy 1.24 (a fallback for the bit-counting function is included and tested); pandas was not installed there at the time.
