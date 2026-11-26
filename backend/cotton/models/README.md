# Cotton classifier model files

| File | What | Where it comes from |
|---|---|---|
| `cotton_svm.joblib`, `metrics.json` | v1: the BTP notebook's SVM on 31 hand-made features | `python backend/cotton/train_classifier.py --data-dir ...` |
| `cotton_v2.joblib`, `metrics_v2.json` | v2 (26 Nov 2026): cotton/not-cotton gate + multi-dataset disease model | `python eval/cotton_v2/train_v2.py --save` (see eval/cotton_v2/) |
| `backbone/convnext_tiny-983f1562.pth` | ImageNet ConvNeXt-Tiny weights (torchvision, BSD-3) | `curl -L -o backbone/convnext_tiny-983f1562.pth https://download.pytorch.org/models/convnext_tiny-983f1562.pth` |
| `clip-vit-base-patch16/` | OpenAI CLIP ViT-B/16 (MIT licence) | the files of https://huggingface.co/openai/clip-vit-base-patch16 (config, preprocessor, tokenizer files, `pytorch_model.bin`) |

The pretrained networks are not stored in git (see .gitignore). `backend/config.py` `COTTON_MODEL_VERSION` picks v1 or v2;
v2 falls back to v1 when its files are missing.
