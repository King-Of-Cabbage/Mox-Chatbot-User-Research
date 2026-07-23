from pathlib import Path

import matplotlib.image as mpimg
import numpy as np


def test_public_figures_have_required_size_and_pixels():
    root = Path(__file__).resolve().parents[1]
    required = {
        "01_sample_screening.png": (1200, 700),
        "02_core_descriptives_ci.png": (1600, 1000),
        "03_correlation_heatmap.png": (1400, 1200),
        "04_model_a_coef_ci.png": (1200, 700),
        "05_model_b_coef_ci.png": (1200, 700),
        "06_model_c_coef_ci.png": (1200, 700),
    }
    for name, (min_w, min_h) in required.items():
        img = mpimg.imread(root / "results" / "figures" / name)
        assert img.shape[1] >= min_w
        assert img.shape[0] >= min_h
        assert float(np.std(img[..., :3])) > 0.01
