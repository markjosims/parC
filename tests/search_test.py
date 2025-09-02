import pynini
from pynini.lib import rewrite
from src.search import *

vowel = pynini.union(*"aeiouə")
consonant = pynini.union(*"ptk")
sigma = pynini.union(vowel, consonant)
substitutions = [
    (vowel, "ə", 0.5),
]
insertions = [
    ("ə", 0.5),
]
deletions = [
    ("ə", 0.5),
    ("t", 0.5),
]
lexicon = [
    "ta",
    "ka",
    "ko",
    "patə",
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
    assert best_string == "ko"
