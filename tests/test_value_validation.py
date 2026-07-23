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


def test_raw_likert_integer_only_rejects_decimal_values():
    with pytest.raises(AnalysisValidationError):
        validate_likert_series(pd.Series([1, 2.5, 5]), "raw_item", integer_only=True)


def test_demo_composite_likert_accepts_decimal_values():
    out = validate_likert_series(pd.Series([1, 3.5, 5]), "demo_composite", integer_only=False)
    assert out.tolist() == [1, 3.5, 5]
