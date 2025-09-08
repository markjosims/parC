import pytest
from src.phonology import *
from pynini.lib import rewrite

@pytest.mark.parametrize("fst_input,fst_output", [
    ("àpɾí",                "námàl"),
    ("àpɾí", ["námàl",      "nàpɾí"]),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    ["námàl", "nàpɾí"]),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    "námàl"),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    None),
    ("ðɔ̀mɔ̀cɔ̀",              None),
])
def test_fst_wrapper(fst_input, fst_output):
    f = fst(fst_input, fst_output)
    input_strings = get_decoded_strings(f, 'input')
    if type(fst_input) is str:
        assert len(input_strings) == 1
        assert input_strings[0] == fst_input
    else:
        assert set(input_strings) == set(fst_input)

    if fst_output is None:
        return

    output_strings = get_decoded_strings(f, 'output')
    if type(fst_output) is str:
        assert len(output_strings) == 1
        assert output_strings[0] == fst_output
    else:
        assert set(output_strings) == set(fst_output)

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "ŕn"),
    ("tutɔ", "tútɔ́"),
    ("kaŋt̪ɛt̪iŋi", "káŋt̪ɛ́t̪íŋí"),
    ("kr", "kŕ")
])
def test_all_high_tone(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), ALL_HIGH_TONE_RULE)
    strings = get_decoded_strings(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "r̀n"),
    ("tutɔ", "tùtɔ̀"),
    ("kaŋt̪ɛt̪iŋi", "kàŋt̪ɛ̀t̪ìŋì"),
    ("kr", "kr̀")
])
def test_all_low_tone(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), ALL_LOW_TONE_RULE)
    strings = get_decoded_strings(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "ŕn"),
    ("tutɔ", "tútɔ̀"),
    ("kaŋt̪ɛt̪iŋi", "káŋt̪ɛ̀t̪ìŋì"),
    ("kr", "kŕ")
])
def test_hlstar(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), HLSTAR_RULE)
    strings = get_decoded_strings(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str