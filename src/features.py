"""
TODO: Script that defines feature sets for inflectional paradigms
for nouns and verbs in Tira.
"""

from pynini.lib import features

CLASS_PREFIXES = [
    "j",
    "g",
    "t̪",
    "ð",
    "n",
    "ɲ",
    "ŋ",
    "r",
    "l",
]
CLASS_AGREE = features.Feature("class", *CLASS_PREFIXES)

TAM = features.Feature(
    "tam",
    "imperfective",
    "perfective",
    "dependent",
    "infinitive",
    "imperative"
)
DEIXIS = features.Feature("deixis", "ventive", "itive")

INFLECTED_VERB = features.Category(TAM, DEIXIS, CLASS_AGREE)