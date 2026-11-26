"""
Turns a photo into a list of numbers with a frozen, pretrained image network.
The network is never retrained here; small models trained on top of these
numbers do the cotton work (eval/cotton_v2/train_v2.py).

Two backbones, both stored under backend/cotton/models/ so the app works offline:
  'convnext' : torchvision ConvNeXt-Tiny trained on ImageNet-1k, 768 numbers
  'clip'     : OpenAI CLIP ViT-B/16 image tower (transformers), 512 numbers
Every vector is L2-normalised.
"""

import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
IMAGE_SIZE = 224
BACKBONES = {
    'convnext': {'dim': 768, 'path': os.path.join(MODELS, 'backbone', 'convnext_tiny-983f1562.pth'),
                 'mean': [0.485, 0.456, 0.406], 'std': [0.229, 0.224, 0.225]},
    'clip': {'dim': 512, 'path': os.path.join(MODELS, 'clip-vit-base-patch16'),
             'mean': [0.48145466, 0.4578275, 0.40821073], 'std': [0.26862954, 0.26130258, 0.27577711]},
}


def load_image(path_or_pil):
    """Open, fix EXIF rotation, RGB, shorter side to 224, centre crop 224 x 224."""
    from PIL import Image, ImageOps
    img = path_or_pil if hasattr(path_or_pil, 'size') else Image.open(path_or_pil)
    img = ImageOps.exif_transpose(img).convert('RGB')
    w, h = img.size
    s = IMAGE_SIZE / min(w, h)
    img = img.resize((max(IMAGE_SIZE, round(w * s)), max(IMAGE_SIZE, round(h * s))), Image.BILINEAR)
    w, h = img.size
    left, top = (w - IMAGE_SIZE) // 2, (h - IMAGE_SIZE) // 2
    return img.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))


class Embedder:
    def __init__(self, backbone='convnext', device=None):
        import torch
        cfg = BACKBONES[backbone]
        if not os.path.exists(cfg['path']):
            raise FileNotFoundError(f'Backbone weights missing: {cfg["path"]}')
        if backbone == 'convnext':
            import torchvision
            net = torchvision.models.convnext_tiny(weights=None)
            net.load_state_dict(torch.load(cfg['path'], map_location='cpu'))
            net.classifier[2] = torch.nn.Identity()   # keep LayerNorm + flatten, drop the ImageNet head
            self._forward = net
        else:
            from transformers import CLIPModel
            net = CLIPModel.from_pretrained(cfg['path'], local_files_only=True)
            self._forward = net.get_image_features
        net.eval()
        if device is None:
            device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.net = net.to(device)
        self.device = device
        self.backbone = backbone
        self.dim = cfg['dim']
        self.mean = np.array(cfg['mean'], np.float32)
        self.std = np.array(cfg['std'], np.float32)
        self.torch = torch

    load_image = staticmethod(load_image)

    def embed_images(self, imgs):
        """List of 224 x 224 PIL images -> (n, dim) float32, L2-normalised."""
        arr = np.stack([(np.asarray(i, dtype=np.float32) / 255.0 - self.mean) / self.std for i in imgs])
        x = self.torch.from_numpy(arr.transpose(0, 3, 1, 2).copy()).to(self.device)
        with self.torch.no_grad():
            out = self._forward(x)
        out = out.float().cpu().numpy()
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-8)

    def embed(self, path_or_pil):
        return self.embed_images([load_image(path_or_pil)])[0]
