import pytest
from jride_agent import places


def test_exact_and_alias():
    assert places.resolve("Trinity College")[0] == "Trinity College"
    assert places.resolve("airport")[0] == "Dublin Airport"
    assert places.resolve("  HEUSTON ")[0] == "Heuston Station"


def test_possessive_names_render():
    assert places.resolve("st james's hospital")[0] == "St James's Hospital"


def test_typo_is_fuzzy_matched():
    assert places.resolve("Heuston Staton")[0] == "Heuston Station"


def test_unknown_place_raises_with_hint():
    with pytest.raises(places.PlaceError):
        places.resolve("Narnia")


def test_coordinates_in_and_out_of_area():
    assert places.resolve("53.3438, -6.2546")[1:] == (53.3438, -6.2546)
    with pytest.raises(places.PlaceError):
        places.resolve("0.0, 0.0")
    with pytest.raises(places.PlaceError):
        places.resolve("51.5074, -0.1278")  # London


def test_empty():
    with pytest.raises(places.PlaceError):
        places.resolve("   ")
