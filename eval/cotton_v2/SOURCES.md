# Photo sets used by the v2 cotton classifier (downloaded 26 Nov 2026)

Licences are as shown by Kaggle's or Mendeley's own metadata on 26 Nov 2026. Photo counts after cleaning are in
`eval/results/cotton_v2/report.md` (written by `train_v2.py`; do not copy numbers from anywhere else).
Raw downloads: `~/Downloads/Cottondataset/v2/raw/`. Small copies: `.../v2/img/`. Catalogue: `.../v2/catalog.csv`.

## Cotton (used by the gate as "cotton" and, where the condition is named, by the disease model)

| id | Where | Licence | What it holds | Used |
|---|---|---|---|---|
| own | Project's photos ("Cotton Data set Man Mohan", two Drive zips) | not recorded | 8 folders | all except Boll rot / Root rot (same 35 photos in both) |
| eastwest | Mendeley `t9hgvk2h9p` v1 (Ripon et al. 2025) | CC BY 4.0 | Alternaria, bacterial blight, Fusarium wilt, healthy, Verticillium | originals only |
| severity | Mendeley `74jsdxtmx2` v3 (Shingne et al. 2025) | CC BY 4.0 | healthy, bacterial blight, curl virus, Fusarium wilt | originals only |
| ayaz | Ayaz 2024, Mendeley `6b2wxbs9cv` v2 | CC BY 4.0 | aphids, army worm, bacterial blight, healthy, powdery mildew, target spot (+ boll photos) | up to 400 per folder; boll photos left out |
| sarcld | Mendeley `b3jy2p6k8w` v2 (Bishshash et al. 2024), `Original Dataset.zip` | CC BY 4.0 | bacterial blight, curl virus, healthy, herbicide damage, jassids, leaf reddening, leaf variegation | originals only (the augmented copies are not used) |
| cosev | Mendeley `y7544ghy3y` v1 (CoSEV) | CC BY 4.0 | curl virus stages, healthy, leaf enation, mixed curl + sooty | single-condition folders only (mixed folders left out) |
| janmejay | Kaggle `janmejaybhoi/cotton-disease-dataset` | CC0 | diseased / fresh cotton leaf and plant | gate only for "diseased" (disease not named); "fresh" = Healthy |
| seroshkarim | Kaggle `seroshkarim/cotton-leaf-disease-dataset` | Unknown | bacterial blight, curl virus, Fusarium wilt, healthy | all |
| raaavan | Kaggle `raaavan/cottonleafinfection` | CC0 | same four classes as seroshkarim (likely the same photos; merged as copies) | all |
| fatimacurl | Kaggle `fatimashakeel1/cottonleafcurl-dataset` | MIT | curl leaf, healthy leaf | all |
| dhamur | Kaggle `dhamur/cotton-plant-disease` | Open Database (contents © authors) | re-upload of the Ayaz classes plus processed copies | "Main dataset" and "Cotton plant disease" folders only, up to 300 per folder; black-and-white and HOG copies left out |

Not used: Hugging Face `YaswanthReddy23/Cotton_leaf` (same classes and counts as SAR-CLD originals),
`Ashmita2000/Cotton_Leaves` (199 photos, same folder names as the Ayaz "edited" set), `Francesco/cotton-plant-disease`
(object-detection boxes); Kaggle `shuvokumarbasak2030/cotton-disease-multi-transformation-dataset` (only augmented
copies), `sabuktagin/dataset-for-cotton-leaf-disease-detection` (a re-upload of SAR-CLD).

## Not cotton (gate only)

| id | Where | Licence | Taken |
|---|---|---|---|
| plantvillage | Kaggle `mohitsingh1804/plantvillage` (PlantVillage, 14 crops, no cotton) | GPL 2 (as listed by the uploader) | 45 per class, train split |
| imagenette | fast.ai Imagenette 160 px (10 everyday ImageNet classes) | as ImageNet terms | 90 per class |
| rice | Kaggle `vbookshelf/rice-leaf-diseases` | Unknown | all |
| pumpkin | Kaggle `tahmidmir/pumpkin-leaf-diseases-dataset-from-bangladesh` | CC BY 4.0 | 60 per folder |
| hibiscus | Kaggle `sayooj98/hibiscus-leaf-dataset-small` (same plant family as cotton) | © original authors | 150 per folder |
| cottonweeds | Kaggle `mrumakantamaharana/cottonweedid15-resized-balanced` (weeds photographed in cotton fields) | LGPL 3.0 as listed; original CottonWeedID15 is CC BY-NC 4.0 | 30 per species |
| deepweeds | Kaggle `imsparsh/deepweeds` | CC BY 4.0 | 600 |
| bpld | Kaggle `tinnybiswas/bangladeshi-plant-leave-dataset-bpld` | CC BY 4.0 | 40 per folder |
| cannabis | Kaggle `engineeringubu/leaf-manifestation-diseases-of-cannabis` | CC BY-NC-SA 4.0 | 25 per folder (file-by-file sample) |
| okra | Kaggle `manojgadde/yellow-vein-mosaic-disease` (okra, same plant family as cotton) | © original authors | 120 per folder (sample) |
| medicinal | Kaggle `warcoder/indian-medicinal-leaf-image-dataset` | CC BY 4.0 | 8 per species (sample) |

Several licences are non-commercial or "© original authors": fine for a student project, but check before any
commercial use or redistribution of the photos. The trained model files contain numbers, not photos, except
`cotton_ref` in `cotton_v2.joblib`, which stores the 768 ConvNeXt numbers of each cotton training photo (no pixels).
