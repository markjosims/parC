import pynini
from pynini.lib import rewrite
from src.search import *
import pytest

vowel = pynini.union(*"aeiouə")
consonant = pynini.union(*"ptkʔ")
sigma = pynini.union(vowel, consonant)
substitutions = [
    ("ə", vowel-"ə", 0.5),
    ("p", "k", 0.9),
]
insertions = [
    ("ʔ", 0.5),
]
deletions = [
    ("ə", 0.5),
    ("t", 0.5),
]
lexicon = [
    "ta",
    "ka",
    "ʔa",
    "ko",
    "patə",
    "pə",
]

def test_edit_factors():
    left_factor, right_factor = get_edit_factors(
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=sigma,
        bound=10,
    )
    query = "tə"
    target = "ta"
    output_fst = (query@left_factor)@(right_factor@target)
    string = pynini.shortestpath(output_fst).string()
    assert string == target

def test_searchable_lexicon():
    left_factor, searchable_lexicon = get_searchable_lexicon(
        lexicon=lexicon,
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=sigma,
        bound=10,
    )
    query = "po"
    output_fst = query@left_factor@searchable_lexicon
    strings = rewrite.lattice_to_strings(output_fst)
    strings = set(strings)
    assert strings == set(lexicon)

    best_string = pynini.shortestpath(output_fst).string()
    
    # p>k preferred over other consonant changes
    assert best_string == "ko"

@pytest.mark.parametrize("query,top_string,top_n_strings", [
    ("tka", "ka", ["ta", "ka"]),      # cheaper to delete /t/ than /k/
    ("a", "ʔa", ["ʔa", "ka", "ta"]),  # cheaper to insert /ʔ/ than /k/ or /t/
    ("tə", "ta", ["ta", "pə"]),       # cheaper to substitute a>ə than t>p
])
def test_edit_weight(query, top_string, top_n_strings):
    left_factor, searchable_lexicon = get_searchable_lexicon(
        lexicon=lexicon,
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=sigma,
        bound=10,
    )
    output_fst = query@left_factor@searchable_lexicon
    predicted_top_string = pynini.shortestpath(output_fst).string()
    assert predicted_top_string == top_string

    predicted_top_n_strings = rewrite.top_rewrites(query@left_factor, searchable_lexicon, nshortest=len(top_n_strings))
    assert set(predicted_top_n_strings) == set(top_n_strings)