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
