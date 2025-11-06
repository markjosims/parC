"""
Form builders for verbs with extension suffixes.
Relies on paradigm building functions from `src.form_builders.verb_forms`.
This module defines verb stems with specific extensions, as well as FSA-based
search functions to determine if a given verb form matches a particular extension pattern.
"""

from src.constants import (
    EXTENSION_MAP, ABBREVIATION2EXTENSION, EXTENSION2ABBREVIATION,
    BOUNDARY_STR,
)
from src.lexicon.phonology import LOCATIVE_ROUNDING_RULE
from typing import *
from src.fst_helpers import fst, decode_fst_lattice

def extension_abbreviations_to_long(
    extension_seq: Union[str, Tuple[str, str]]
):
    """
    Arguments:
        extension_seq: A single extension or a tuple of two extensions.
    Returns:
        A list of long-form extension names corresponding to the input.
    """
    if type(extension_seq) == str:
        return ABBREVIATION2EXTENSION[extension_seq]
    else:
        return list(ABBREVIATION2EXTENSION[ext] for ext in extension_seq)
    
def extension_long_to_abbreviations(
    extension_seq: Union[str, Tuple[str, str]]
):
    """
    Arguments:
        extension_seq: A single extension or a tuple of two extensions.
    Returns:
        A list of abbreviation-form extension names corresponding to the input.
    """
    if type(extension_seq) == str:
        return EXTENSION2ABBREVIATION[extension_seq]
    else:
        return list(EXTENSION2ABBREVIATION[ext] for ext in extension_seq)

def get_derived_stem_and_fv(
        base_stem: Union[str, List[str]],
        gloss: Union[str, List[str]],
        fv: str,
        extension_seq: Union[str, Sequence[str]]
) -> Tuple[List[str], List[str], str]:
    """
    Arguments:
        base_stem: The root form of the verb.
        gloss: The gloss of the base verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
    Returns:
        (derived_stem, derived_glosses, derived_fv): The derived verb stem, glosses
        and FV class with the appropriate extensions applied.

    Given a base verb stem and an extension sequence (e.g., 'causative', 'passive'),
    return the derived stem with the appropriate suffixes.
    """
    if type(extension_seq) == str:
        extension_seq = [extension_seq]
    if extension_seq[0] in ABBREVIATION2EXTENSION:
        extension_seq = extension_abbreviations_to_long(extension_seq)
    extension_seq_short = extension_long_to_abbreviations(extension_seq)

    outer_fv = fv
    extension_suffix_str = ''
    for ext in extension_seq:
        suffix = EXTENSION_MAP[ext]
        if type(suffix) is dict:
            suffix_str, suffix_fv = suffix[outer_fv]
            extension_suffix_str+= suffix_str
        else: # type(suffix) is tuple
            suffix_str, suffix_fv = suffix
            extension_suffix_str+= suffix_str
        outer_fv = suffix_fv
    
    if type(base_stem) is str:
        derived_stems = [base_stem + BOUNDARY_STR + extension_suffix_str]
    else:
        derived_stems = [
            stem + BOUNDARY_STR + extension_suffix_str
            for stem in base_stem
        ]
    if type(gloss) is str:
        derived_glosses = [BOUNDARY_STR.join([gloss, *extension_seq_short])]
    else:
        derived_glosses = [
            BOUNDARY_STR.join([g, *extension_seq_short])
            for g in gloss
        ]


    if extension_seq[0] == 'locative':
        # locative extension may assimilate in rounding to the stem vowel
        derived_stems_w_rounding = []
        derived_glosses_w_rounding = []
        for stem, gloss in zip(derived_stems, derived_glosses):
            stem = fst(stem) @ LOCATIVE_ROUNDING_RULE
            new_stems = decode_fst_lattice(stem, strings_only=True)
            derived_stems_w_rounding.extend(new_stems)
            derived_glosses_w_rounding.extend([gloss]*len(new_stems))
        derived_glosses = derived_glosses_w_rounding
        derived_stems = derived_stems_w_rounding
    return derived_stems, derived_glosses, outer_fv