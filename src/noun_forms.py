import pynini
from pynini.lib import features, paradigms, rewrite, pynutil
from src.phonology import *
from src.fst_helpers import *
from src.lexicon import NOUNS_DF, get_noun_lemmata
from src.constants import (
    NOUN_FEATURE_ABBREVIATION_TO_VECTOR,
    NOUN,
    NOMSG,
    BOUNDARY_STR,
)
from typing import *

def build_noun_forms():
    """
    Create Paradigm object for Tira nouns.
    """
    slots = []
    lemma_col = NOUNS_DF['lemma']
    for feature_str, feature_vec in NOUN_FEATURE_ABBREVIATION_TO_VECTOR.items():
        feature_col = NOUNS_DF[feature_str]
        feature_mask = feature_col!=''
        
        feature_forms = feature_col[feature_mask].tolist()
        lemmata = lemma_col[feature_mask].tolist()
        feature_fsts = []

        for form, lemma in zip(feature_forms, lemmata):
            for subform in form.split():
                feature_fsts.append(fst(lemma, subform))
        feature_fst = pynini.union(*feature_fsts).optimize()
        slots.append((feature_fst, feature_vec))
    noun_paradigm = paradigms.Paradigm(
        category=NOUN,
        name='Nouns',
        slots=slots,
        lemma_feature_vector=NOMSG,
        stems=get_noun_lemmata(wrap_w_fsa=True),
        boundary=fst(BOUNDARY_STR),
    )
    return noun_paradigm

NOUN_PARADIGM = build_noun_forms()