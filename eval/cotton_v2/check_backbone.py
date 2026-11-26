"""Load the local ConvNeXt-Tiny backbone and time it. Run: python eval/cotton_v2/check_backbone.py"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

from PIL import Image  # noqa: E402

from cotton.embedder import Embedder  # noqa: E402

e = Embedder()
imgs = [Image.new('RGB', (224, 224), (40 + i, 120, 60)) for i in range(64)]
e.embed_images(imgs[:4])
t = time.time()
f = e.embed_images(imgs)
print(e.device, f.shape, f'{time.time() - t:.2f} s for 64 images')
