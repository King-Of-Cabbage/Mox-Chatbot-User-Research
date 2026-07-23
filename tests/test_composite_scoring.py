import math
import pandas as pd

from src.run_analysis import score_composite


def test_bank_service_min_four_items():
    frame = pd.DataFrame({"a": [1, 1], "b": [2, None], "c": [3, 3], "d": [4, 4], "e": [None, None]})
    score, counts = score_composite(frame, min_valid=4)
    assert score.iloc[0] == 2.5
    assert math.isnan(score.iloc[1])
    assert counts.tolist() == [4, 3]


def test_security_control_requires_both_items():
    frame = pd.DataFrame({"security": [4, 4], "control": [5, None]})
    score, counts = score_composite(frame, min_valid=2)
    assert score.iloc[0] == 4.5
    assert math.isnan(score.iloc[1])
    assert counts.tolist() == [2, 1]
