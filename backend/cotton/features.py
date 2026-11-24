"""
Feature extraction for the cotton leaf-disease classifier.

This is the pipeline from the project notebook, copied function-for-function
(no plotting): resize 224x224 -> bilateral filter -> lesion mask
(inverse Otsu AND NOT green) -> 31 features
(12 GLCM + 10 uniform LBP + 9 RGB colour moments).

Do not change anything here without retraining: the saved model expects exactly
these 31 numbers in this order.
"""

import cv2
import numpy as np
from scipy.stats import skew
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

N_FEATURES = 31


def preprocess_and_segment(image_path, target_size=(224, 224)):
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Could not load image at: {image_path}")
    img_bgr = cv2.resize(img_bgr, target_size)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    bilateral_rgb = cv2.bilateralFilter(img_rgb, d=9, sigmaColor=75, sigmaSpace=75)

    hsv = cv2.cvtColor(bilateral_rgb, cv2.COLOR_RGB2HSV)
    green_leaf_mask = cv2.inRange(hsv, np.array([25, 35, 35]), np.array([85, 255, 255]))

    gray = cv2.cvtColor(bilateral_rgb, cv2.COLOR_RGB2GRAY)
    _, otsu_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    raw_lesion_mask = cv2.bitwise_and(otsu_mask, cv2.bitwise_not(green_leaf_mask))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean_mask = cv2.morphologyEx(raw_lesion_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_DILATE, kernel, iterations=1)

    if np.sum(clean_mask) == 0:
        clean_mask = otsu_mask

    segmented_roi = cv2.bitwise_and(gray, gray, mask=clean_mask)
    return bilateral_rgb, clean_mask, segmented_roi


def extract_single_image_features(image_path):
    filtered_rgb, mask, segmented_gray = preprocess_and_segment(image_path)

    # A. GLCM (12)
    quantized_gray = (segmented_gray // 8).astype(np.uint8)
    distances = [1, 2]
    angles = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]
    props = ['contrast', 'dissimilarity', 'homogeneity', 'energy', 'correlation', 'ASM']
    glcm = graycomatrix(quantized_gray, distances=distances, angles=angles,
                        levels=32, symmetric=True, normed=True)
    glcm_features = []
    for prop in props:
        vals = graycoprops(glcm, prop)
        glcm_features.append(float(vals.mean()))
        glcm_features.append(float(vals.std()))

    # B. Uniform LBP (10)
    P, R = 8, 1
    lbp = local_binary_pattern(segmented_gray, P, R, method='uniform')
    lesion_lbp = lbp[mask > 0]
    if len(lesion_lbp) == 0:
        lesion_lbp = lbp.ravel()
    lbp_hist, _ = np.histogram(lesion_lbp, bins=np.arange(0, P + 3), range=(0, P + 2))
    lbp_hist = lbp_hist.astype('float')
    lbp_hist /= (lbp_hist.sum() + 1e-6)

    # C. Colour moments (9)
    color_moments = []
    for c in range(3):
        vals = filtered_rgb[:, :, c][mask > 0]
        if len(vals) == 0:
            vals = filtered_rgb[:, :, c].ravel()
        color_moments.extend([float(np.mean(vals)), float(np.std(vals)), float(skew(vals))])

    feats = np.hstack([glcm_features, lbp_hist, color_moments])
    # skew() of a constant channel is NaN; a NaN would crash the SVM.
    return np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
