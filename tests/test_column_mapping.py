import pytest

from src.run_analysis import FIELD_REGISTRY, AnalysisValidationError, locate_columns, normalize_header


def _headers():
    return [spec["exact"][0] for spec in FIELD_REGISTRY.values()]


def test_exact_column_mapping():
    mapping = locate_columns(_headers())
    assert mapping["q10_security"] == FIELD_REGISTRY["q10_security"]["exact"][0]
    assert mapping["bank_trust_outcome"] == FIELD_REGISTRY["bank_trust_outcome"]["exact"][0]


def test_normalization_allows_spacing_and_punctuation_variants():
    headers = _headers()
    original = FIELD_REGISTRY["q10_control"]["exact"][0]
    headers[headers.index(original)] = "  " + original.replace("\uff1a", ":") + "  "
    assert locate_columns(headers)["q10_control"].strip()


def test_missing_and_duplicate_columns_fail_safely():
    headers = _headers()
    headers.remove(FIELD_REGISTRY["duration"]["exact"][0])
    with pytest.raises(AnalysisValidationError, match="duration"):
        locate_columns(headers)
    dup = _headers() + [_headers()[0]]
    with pytest.raises(AnalysisValidationError, match="Duplicate"):
        locate_columns(dup)


def test_normalize_header_nfkc():
    text = "\uff11\uff10\uff1a\u6d4b\u8bd5"
    assert normalize_header(f"  {text}  ") == "10:\u6d4b\u8bd5"
