from pynini.lib import paradigms, features
from typing import *
from src.cache_decorators import output_cache
from src.lexicon import get_adjective_roots, get_gloss_for_adjective, get_all_adjective_data
from src.form_builders.form_helpers import add_class_prefix, add_class_prefixes_to_slots
from src.constants import ADJECTIVE, ADJECTIVE_ROOT, ADJECTIVE_CLASS_VALUES, BOUNDARY_STR
from src.lexicon.phonology import ALL_LOW_TONE_RULE, SIGMASTAR
from src.fst_helpers import decode_byte_str, decode_fst_string, fst, stringify_lexeme_features
import pandas as pd

@output_cache(__file__)
def get_adjective_paradigm() -> paradigms.Paradigm:
    adj_df = get_all_adjective_data(return_type=pd.DataFrame)
    adj_lemmata = get_adjective_roots(wrap_w_fsa=True)

    inflected_slot = (ALL_LOW_TONE_RULE, ADJECTIVE_ROOT)
    root_slot = (SIGMASTAR, ADJECTIVE_ROOT)

    slots = [root_slot]
    slots += add_class_prefixes_to_slots([inflected_slot])
    adj_paradigm = paradigms.Paradigm(
        category=ADJECTIVE,
        slots=slots,
        stems=adj_lemmata,
        boundary=fst(BOUNDARY_STR),
        lemma_feature_vector=ADJECTIVE_ROOT,
        name=stringify_lexeme_features({"part_of_speech": 'adjective'}),
    )
    return adj_paradigm

def parse_adjective(form: str, add_gloss: bool=True) -> Dict[str, str]:
    """
    Arguments:
        form:       str of inflected adjective form
    Returns:        dict of shape {'root': root, '$feature': feature_value}
    """
    parses = []

    adjective_paradigm = get_adjective_paradigm()
    lemmata = adjective_paradigm.lemmatize(fst(form))
    analyzed_forms = adjective_paradigm.analyze(fst(form))
    for lemma, analyzed_form in zip(lemmata, analyzed_forms):
        root, feature_vec = lemma
        root = decode_byte_str(root)

        analyzed_form = analyzed_form[0]
        analyzed_form = decode_byte_str(analyzed_form)

        parse = feature_vec.values
        parse['root'] = root
        parse['analyzed_form'] = analyzed_form
        parse['form'] = form
        if add_gloss:
            parse['gloss']=get_gloss_for_adjective(root)
        parses.append(parse)
    return parses

def inflect_adjective_with_features(root: str, agree_class: str) -> str:
    """
    Arguments:
        root:           str indicating adjective root to inflect
        agree_class:    dict mapping feature labels to values
    Returns:
        form:       str of root adjective inflected with given features
    """
    adjective_paradigm = get_adjective_paradigm()
    slot_for_class = [
        slot for slot in adjective_paradigm.slots if slot[1].values['class'] == agree_class
    ][0]
    rule, _ = slot_for_class
    form = decode_fst_string(fst(root)@rule)

    return form