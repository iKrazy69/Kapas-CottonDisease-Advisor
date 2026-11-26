"""
Loads the trained cotton-disease model and turns an image into a decision.

The decision is deliberately conservative. The model behind it is weak (see
backend/cotton/models/metrics.json after training), so a prediction is only
reported as 'confident' when BOTH hold:
  - its top probability >= Config.COTTON_MIN_PROBABILITY
  - its class has a test F1 >= Config.COTTON_MIN_CLASS_F1 in metrics.json
Otherwise the status is 'uncertain' and the caller must not present it as a
diagnosis.
"""

import json
import logging
import os

from config import Config

logger = logging.getLogger(__name__)


class CottonClassifierUnavailable(Exception):
    pass


class CottonClassifier:
    def __init__(self, model_path=None, metrics_path=None):
        model_path = model_path or Config.COTTON_MODEL_PATH
        metrics_path = metrics_path or Config.COTTON_METRICS_PATH
        if not os.path.exists(model_path):
            raise CottonClassifierUnavailable(
                'Cotton model not found. Train it first: python backend/cotton/train_classifier.py '
                '--data-dir "<your dataset folder>"')
        import joblib
        bundle = joblib.load(model_path)
        self.scaler = bundle['scaler']
        self.model = bundle['model']
        self.class_names = list(bundle['class_names'])
        self.metrics = None
        if os.path.exists(metrics_path):
            with open(metrics_path) as fh:
                self.metrics = json.load(fh)
        else:
            logger.warning('metrics.json missing: per-class reliability cannot be checked')
        logger.info(f'Cotton classifier loaded: {len(self.class_names)} classes')

    def class_f1(self, name):
        if not self.metrics:
            return None
        return self.metrics.get('per_class', {}).get(name, {}).get('f1')

    def is_healthy(self, name):
        return name.strip().lower().startswith('healthy')   # folder is named 'Healthy Plants'

    def predict(self, image_path):
        from cotton.features import extract_single_image_features
        feats = extract_single_image_features(image_path).reshape(1, -1)
        proba = self.model.predict_proba(self.scaler.transform(feats))[0]
        classes = [self.class_names[int(c)] for c in self.model.classes_]
        ranked = sorted(zip(classes, proba), key=lambda t: -t[1])
        top_name, top_p = ranked[0]
        f1 = self.class_f1(top_name)

        reasons = []
        if top_p < Config.COTTON_MIN_PROBABILITY:
            reasons.append(f'top probability {top_p:.2f} is below {Config.COTTON_MIN_PROBABILITY:.2f}')
        if f1 is None:
            reasons.append('no test metrics available for this class')
        elif f1 < Config.COTTON_MIN_CLASS_F1:
            reasons.append(f'the model is unreliable for this class (test F1 {f1:.2f})')

        return {
            'status': 'confident' if not reasons else 'uncertain',
            'reasons': reasons,
            'disease': top_name,
            'probability': float(top_p),
            'class_test_f1': f1,
            'top3': [{'disease': n, 'probability': float(p)} for n, p in ranked[:3]],
        }


class CottonClassifierV2(CottonClassifier):
    """
    v2 (26 Nov 2026, after the presentation): frozen ImageNet ConvNeXt-Tiny
    features (backend/cotton/embedder.py) with two small models trained on
    12 cotton photo sets plus non-cotton photos (eval/cotton_v2/).

    Step 1, the gate: is this a cotton leaf/plant photo at all? Both must hold:
      - the gate model's p(cotton) >= gate_rule['p_min']
      - the photo is close enough to real cotton training photos
        (mean cosine to the 5 nearest >= gate_rule['knn_min'])
    If not, status 'not_cotton' and no disease is named.
    Step 2, the same two checks as v1 (top probability, class F1) on the disease model.
    """

    def __init__(self, model_path=None, metrics_path=None, embed_fn=None):
        model_path = model_path or Config.COTTON_V2_MODEL_PATH
        metrics_path = metrics_path or Config.COTTON_V2_METRICS_PATH
        if not os.path.exists(model_path):
            raise CottonClassifierUnavailable(
                'Cotton v2 model not found. Train it: python eval/cotton_v2/train_v2.py --save')
        import joblib
        import numpy as np
        b = joblib.load(model_path)
        self.np = np
        self.gate = b['gate']
        self.gate_rule = b['gate_rule']
        self.cotton_ref = np.asarray(b['cotton_ref'], dtype=np.float32)
        self.model = b['disease']
        self.class_names = list(b['class_names'])
        self.features = list(b.get('features', ['convnext']))
        tf = b.get('text_features')
        self.text_features = None if tf is None else np.asarray(tf, dtype=np.float32)
        self.logit_scale = float(b.get('logit_scale', 100.0))
        self.n_cotton_prompts = int(b.get('n_cotton_prompts', 0))
        self.version = 2
        self.metrics = None
        if os.path.exists(metrics_path):
            with open(metrics_path) as fh:
                self.metrics = json.load(fh)
        self._embed_fn = embed_fn
        logger.info(f'Cotton classifier v2 loaded: {len(self.class_names)} classes')

    def _embed(self, image_path):
        """Returns (features as train_v2.py built them, the CLIP vector or None).
        A test can inject embed_fn returning either a vector or such a pair."""
        np = self.np
        if self._embed_fn is None:
            from cotton.embedder import Embedder, load_image
            nets = {f: Embedder(f) for f in dict.fromkeys(self.features + (['clip'] if self.text_features is not None else []))}
            scale = 1.0 / np.sqrt(len(self.features))

            def fn(path):
                img = load_image(path)
                vec = {f: n.embed_images([img])[0] for f, n in nets.items()}
                return np.concatenate([vec[f] for f in self.features]) * scale, vec.get('clip')
            self._embed_fn = fn
        out = self._embed_fn(image_path)
        x, clip = out if isinstance(out, tuple) else (out, None)
        return np.asarray(x, dtype=np.float32), (None if clip is None else np.asarray(clip, dtype=np.float32))

    def zero_shot_share(self, clip_vec):
        """CLIP's own share for the cotton text prompts (same as eval/cotton_v2/zeroshot_check.py)."""
        if clip_vec is None or self.text_features is None:
            return None
        np = self.np
        logits = self.logit_scale * (self.text_features @ clip_vec)
        p = np.exp(logits - logits.max())
        p /= p.sum()
        return float(p[:self.n_cotton_prompts].sum())

    def cotton_check(self, x, clip_vec=None):
        np = self.np
        p = float(self.gate.predict_proba(x.reshape(1, -1))[0, list(self.gate.classes_).index(1)])
        sims = self.cotton_ref @ x
        k = min(5, len(sims))
        knn = float(np.sort(sims)[-k:].mean())
        return p, knn, self.zero_shot_share(clip_vec)

    def predict(self, image_path):
        x, clip_vec = self._embed(image_path)
        p_cotton, knn, zs = self.cotton_check(x, clip_vec)
        rule = self.gate_rule
        z_min = rule.get('z_min', 0.0)
        reasons = []
        if p_cotton < rule['p_min']:
            reasons.append(f'cotton score {p_cotton:.2f} is below {rule["p_min"]:.2f}')
        if knn < rule['knn_min']:
            reasons.append('the photo is unlike any cotton photo the model was trained on')
        if zs is not None and zs < z_min:
            reasons.append('the general image model does not see a cotton plant in the photo')
        if reasons:
            return {'status': 'not_cotton', 'reasons': reasons, 'disease': None,
                    'probability': p_cotton, 'cotton_score': p_cotton, 'cotton_similarity': knn,
                    'zero_shot_cotton': zs, 'class_test_f1': None, 'top3': []}

        proba = self.model.predict_proba(x.reshape(1, -1))[0]
        classes = [self.class_names[int(c)] for c in self.model.classes_]
        ranked = sorted(zip(classes, proba), key=lambda t: -t[1])
        top_name, top_p = ranked[0]
        f1 = self.class_f1(top_name)
        reasons = []
        if top_p < Config.COTTON_MIN_PROBABILITY:
            reasons.append(f'top probability {top_p:.2f} is below {Config.COTTON_MIN_PROBABILITY:.2f}')
        if f1 is None:
            reasons.append('no test metrics available for this class')
        elif f1 < Config.COTTON_MIN_CLASS_F1:
            reasons.append(f'the model is unreliable for this class (test F1 {f1:.2f})')
        return {
            'status': 'confident' if not reasons else 'uncertain',
            'reasons': reasons,
            'disease': top_name,
            'probability': float(top_p),
            'cotton_score': p_cotton,
            'cotton_similarity': knn,
            'zero_shot_cotton': zs,
            'class_test_f1': f1,
            'top3': [{'disease': n, 'probability': float(p)} for n, p in ranked[:3]],
        }


def load_cotton_classifier():
    """The version named by Config.COTTON_MODEL_VERSION; v2 falls back to v1 if its files are missing."""
    if getattr(Config, 'COTTON_MODEL_VERSION', 'v1') == 'v2':
        try:
            return CottonClassifierV2()
        except CottonClassifierUnavailable as e:
            logger.warning(f'{e} Falling back to the v1 SVM.')
    return CottonClassifier()
