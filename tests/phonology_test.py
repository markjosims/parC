import pytest
from src.phonology import *
from pynini.lib import rewrite

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "ŕn"),
    ("tutɔ", "tútɔ́"),
    ("kaŋt̪ɛt̪iŋi", "káŋt̪ɛ́t̪íŋí"),
    ("kr", "kŕ")
])
def test_all_high_tone(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(atonal_str, ALL_HIGH_TONE_RULE)
    strings = rewrite.lattice_to_strings(lattice)
    strings = set(strings)
    assert len(strings)==1
    string=strings.pop()
    assert string==tone_added_str