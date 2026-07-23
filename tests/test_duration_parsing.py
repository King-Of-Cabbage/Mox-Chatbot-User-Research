import math

from src.run_analysis import parse_duration_seconds


def test_duration_supported_formats():
    assert parse_duration_seconds(126) == 126
    assert parse_duration_seconds("02:06") == 126
    assert parse_duration_seconds("01:02:03") == 3723
    assert parse_duration_seconds("2\u520630\u79d2") == 150
    assert parse_duration_seconds("1\u65f62\u52063\u79d2") == 3723
    assert parse_duration_seconds("1 hour 2 minutes 3 seconds") == 3723
    assert parse_duration_seconds("1 hr 2 min 3 sec") == 3723


def test_duration_rejects_invalid_values():
    assert math.isnan(parse_duration_seconds(None))
    assert math.isnan(parse_duration_seconds(""))
    assert math.isnan(parse_duration_seconds("-1"))
    assert math.isnan(parse_duration_seconds("1:99"))
    assert math.isnan(parse_duration_seconds("abc"))
