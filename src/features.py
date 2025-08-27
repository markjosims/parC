"""
TODO: Script that defines feature sets for inflectional paradigms
for nouns and verbs in Tira.
"""

from pynini.lib import features

# class prefixes

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
CLASS_AGREE = features.Feature("class", *CLASS_PREFIXES+['unmarked'])

# verb features

SUBJECT_AND_DEIXIS_MARKED_TAM = [
    "imperfective",
    "perfective",
    "dependent",
]
DEIXIS_MARKED_TAM = [
    "imperative"
]
NONFINITE_TAM = [
    "infinitive",
]

TAM = features.Feature("tam", *SUBJECT_AND_DEIXIS_MARKED_TAM, *DEIXIS_MARKED_TAM, *NONFINITE_TAM)

DEIXIS_VALUES = ["ventive", "itive"]
DEIXIS = features.Feature("deixis", "unmarked", *DEIXIS_VALUES)

INFLECTED_VERB = features.Category(TAM, DEIXIS, CLASS_AGREE)

VERB_PARADIGM_SIZE = len(SUBJECT_AND_DEIXIS_MARKED_TAM)*len(CLASS_PREFIXES)*len(DEIXIS_VALUES) +\
    len(DEIXIS_MARKED_TAM)*len(DEIXIS_VALUES)+\
    len(NONFINITE_TAM)

# verb feature bundles

INFINITIVE = features.FeatureVector(INFLECTED_VERB, "tam=infinitive", "class=ð", "deixis=unmarked")
IPFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=itive")
IPFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=ventive")
PFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=itive")
PFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=ventive")
DEP_IT = features.FeatureVector(INFLECTED_VERB, "tam=dependent", "deixis=itive")
DEP_VENT = features.FeatureVector(INFLECTED_VERB, "tam=dependent", "deixis=ventive")
IMP_IT = features.FeatureVector(INFLECTED_VERB, "tam=imperative", "deixis=itive", "class=unmarked")
IMP_VENT = features.FeatureVector(INFLECTED_VERB, "tam=imperative", "deixis=ventive", "class=unmarked")