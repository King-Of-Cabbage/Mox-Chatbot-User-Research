import numpy as np
import pandas as pd
import pytest

from src.run_analysis import AnalysisValidationError, validate_likert_series


def test_likert_accepts_range_empty_and_string_numbers():
    out = validate_likert_series(pd.Series([1, "2", 3, "", None, 5]), "x")
    assert out.dropna().tolist() == [1, 2, 3, 5]


def test_likert_rejects_bad_values():
    for values in ([0], [6], ["bad"], [np.inf], [-np.inf]):
        with pytest.raises(AnalysisValidationError):
            validate_likert_series(pd.Series(values), "x")
