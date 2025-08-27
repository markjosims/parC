import pytest
from src.forms import *
from src.lexicon import get_all_verb_roots_and_fvs
from src.features import VERB_PARADIGM_SIZE

@pytest.mark.parametrize("verb_root,fv_class", get_all_verb_roots_and_fvs())
def test_compile_regular_paradigms(verb_root, fv_class):
    if fv_class == 'IRREG':
        return
    try:
        forms = generate_forms(verb_root, FV2PARADIGM[fv_class], return_wordforms=True)
        assert len(forms) >= VERB_PARADIGM_SIZE
    except Exception as error:
        print(verb_root, fv_class)
        raise error