"""
Form builders for verbs with extension suffixes.
Relies on paradigm building functions from `src.form_builders.verb_forms`.
This module defines verb stems with specific extensions, as well as FSA-based
search functions to determine if a given verb form matches a particular extension pattern.
"""

from src.cache_decorators import output_cache
from src.constants import EXTENSION_MAP, ABBREVIATION2EXTENSION, BOUNDARY_STR, FV_CLASSES
from src.form_builders.verb_forms import get_verb_stem_paradigm, get_verb_paradigm_w_aux, inflect_verb_with_features
from src.lexicon import get_roots_for_class
from src.phonology import LOCATIVE_ROUNDING_RULE
from itertools import product
from typing import *
from pynini.lib import paradigms

from src.fst_helpers import decode_fst_string, fst, decode_fst_lattice

def get_possible_extension_seqs() -> List[List[str]]:
    """
    Returns:
        A list of all possible extension sequences (single and double extensions).
    """
    extension_couples = list(
        product(EXTENSION_MAP.keys(), repeat=2)
    )
    allowed_repeats = ['locative', 'benefactive']
    filtered_extension_couples = [
        couple for couple in extension_couples
        if couple[0] != couple[1] or couple[0] in allowed_repeats
    ]
    single_extensions = [[ext] for ext in EXTENSION_MAP.keys()]
    all_extension_seqs = single_extensions + filtered_extension_couples
    return all_extension_seqs

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

def get_derived_stem_and_fv(
        base_stem: Union[str, List[str]],
        fv: str,
        extension_seq: Union[str, Sequence[str]]
) -> Tuple[List[str], str]:
    """
    Arguments:
        base_stem: The root form of the verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
    Returns:
        (derived_stem, derived_fv): The derived verb stem and FV class
        with the appropriate extensions applied.

    Given a base verb stem and an extension sequence (e.g., 'causative', 'passive'),
    return the derived stem with the appropriate suffixes.
    """
    if type(extension_seq) == str:
        extension_seq = [extension_seq]
    if extension_seq[0] in ABBREVIATION2EXTENSION:
        extension_seq = extension_abbreviations_to_long(extension_seq)
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
    if extension_seq[0] == 'locative':
        derived_stems_w_rounding = []
        for stem in derived_stems:
            stem = fst(stem) @ LOCATIVE_ROUNDING_RULE
            new_stems = decode_fst_lattice(stem)
            derived_stems_w_rounding.extend(new_stems)
        derived_stems = derived_stems_w_rounding
    return derived_stems, outer_fv

def get_paradigm_for_extension(
    fv: str,
    extension_seq: Union[str, Sequence[str], None],
    root: Optional[str]=None,
) -> Tuple[paradigms.Paradigm, paradigms.Paradigm]:
    """
    Arguments:
        fv:             FV class for verb.
        extension_seq:  A single extension or a sequence of extensions to apply.
        root:           The root form of the verb.
                        If none, load all roots for the FV class.
    Returns:
        (paradigm_no_aux, paradigm_w_aux):
        A mapping from grammatical feature strings to inflected verb forms.

    Build the full paradigm for a verb with the specified extensions applied.
    """
    if root is None:
        root = get_roots_for_class(fv)
    derived_stem, derived_fv = get_derived_stem_and_fv(root, fv, extension_seq)
    paradigm_name = f"fv={derived_fv} ext={'+'.join(extension_seq)}"
    if root is not None:
        paradigm_name += f" stem={'/'.join(derived_stem)}"
    paradigm_no_aux = get_verb_stem_paradigm(
        stems=derived_stem,
        fv_class=derived_fv,
        paradigm_name=paradigm_name
    )
    paradigm_w_aux = get_verb_paradigm_w_aux(paradigm_no_aux)
    return paradigm_no_aux, paradigm_w_aux

def get_paradigms_for_all_extensions() -> Dict[str, Tuple[paradigms.Paradigm, paradigms.Paradigm]]:
    """
    Returns:
        A mapping from extension sequences to their corresponding paradigms
        (with and without auxiliary verbs).

    Build paradigms for all possible extension sequences.
    Note: Due to the way paradigm building is handled, the key is the FV for
    the derived verb, not the verb root.
    """
    fv_to_stems, fv_to_ext_seqs = map_fv_to_derived_stems()
    paradigms_for_extensions = {}
    for fv, stems in fv_to_stems.items():
        extensions_seqs = fv_to_ext_seqs[fv]
        paradigm_no_aux = get_verb_stem_paradigm(
            stems=stems,
            fv_class=fv,
            paradigm_name=f"fv={fv} ext={'/'.join(extensions_seqs)}"
        )
        paradigm_w_aux = get_verb_paradigm_w_aux(paradigm_no_aux)
        paradigms_for_extensions[fv] = (paradigm_no_aux, paradigm_w_aux)
    return paradigms_for_extensions

@output_cache(__file__)
def map_fv_to_derived_stems():
    all_extension_seqs = get_possible_extension_seqs()
    fv_to_stems = {fv: [] for fv in FV_CLASSES}
    fv_to_ext_seqs = {fv: set() for fv in FV_CLASSES}
    for fv in FV_CLASSES:
        fv_roots = get_roots_for_class(fv)
        for extension_seq in all_extension_seqs:
            derived_stems, derived_fv = get_derived_stem_and_fv(
                base_stem=fv_roots,
                fv=fv,
                extension_seq=extension_seq
            )
            fv_to_stems[derived_fv].extend(derived_stems)
            extension_seq_str = '+'.join(extension_seq)
            fv_to_ext_seqs[derived_fv].add(extension_seq_str)
    for fv in FV_CLASSES:
        fv_to_ext_seqs[fv] = sorted(list(fv_to_ext_seqs[fv]))
        fv_to_stems[fv] = sorted(list(fv_to_stems[fv]))
    return fv_to_stems,fv_to_ext_seqs

def inflect_verb_with_extension(
    root: str,
    fv: str,
    extension_seq: Union[str, Sequence[str]],
    features: Dict[str, str],
    expected_verb_type: Literal['stem', 'stem_and_aux', 'all']='all',
) -> List[str]:
    """
    Arguments:
        root: The root form of the verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
        features: A dict mapping feature labels to values.
        expected_verb_type: The expected type of the verb ('stem', 'stem_and_aux', 'all').
    Returns:
        A list of inflected verb forms with the specified extensions applied.

    Inflect a verb with the given extensions and return all possible forms.
    """
    paradigm_no_aux, paradigm_w_aux = get_paradigm_for_extension(
        root, fv, extension_seq
    )
    derived_stem = paradigm_no_aux.stems
    derived_stem = decode_fst_string(derived_stem)
    if expected_verb_type == 'stem':
        return inflect_verb_with_features(derived_stem, paradigm_no_aux, features=features)
    elif expected_verb_type == 'stem_and_aux':
        return inflect_verb_with_features(derived_stem, paradigm_w_aux, features=features)
    else:  # expected_verb_type == 'all'        
        forms_no_aux = inflect_verb_with_features(derived_stem, paradigm_no_aux, features=features)
        forms_w_aux = inflect_verb_with_features(derived_stem, paradigm_w_aux, features=features)
        return forms_no_aux + forms_w_aux   
   