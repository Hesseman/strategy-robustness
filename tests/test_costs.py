from robustness.costs import PER_SIDE_USD, normalize_root, round_trip_usd


def test_table_is_the_multiwalk_list():
    assert len(PER_SIDE_USD) == 79
    assert PER_SIDE_USD["ES"] == (2.5, 12.5)
    assert PER_SIDE_USD["MNQ"] == (0.62, 2.25)
    assert PER_SIDE_USD["QN"] == (0.62, 6.5625)


def test_normalize_root():
    assert normalize_root("@MNQ") == "MNQ"
    assert normalize_root("MNQZ26") == "MNQ"
    assert normalize_root("esz26") == "ES"
    assert normalize_root("NE1") == "NE1"
    assert normalize_root("@M6E") == "M6E"
    assert normalize_root("FGBL") == "FGBL"


def test_round_trip():
    assert round_trip_usd("@MNQ") == 5.74
    assert round_trip_usd("ES") == 30.0
    assert round_trip_usd("NQ") == 35.0
    assert round_trip_usd("XYZ") is None
