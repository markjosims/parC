from src.form_builders.main_parser import get_main_parser, inflect_word, parse_word
from src.lexicon.lexicon import *
from src.constants import VERB_FEATURE_VALUES, LEXICAL_FEATURE_VALUES
import pytest

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_inflection(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    gold_verb["part_of_speech"]='verb'

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if k in VERB_FEATURE_VALUES+LEXICAL_FEATURE_VALUES
    }
    predicted_form = inflect_word(root, features=gold_verb_filtered)

    assert form in predicted_form

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing(gold_verb):
    analyzed_form = gold_verb['form']
    gold_verb['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_verb['form']=form

    predicted_parse = parse_word(form)
    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if any(k in parse for parse in predicted_parse)
    }
    assert gold_verb_filtered in predicted_parse

@pytest.mark.parametrize("gold_verb", get_gold_derived_verbs())
def test_derived_verbs(gold_verb):
    form = gold_verb.pop('form')
    root = gold_verb.pop('root')
    gold_verb["part_of_speech"]='verb'

    verb_filtered = {
        k: v for k,v in gold_verb.items()
        if k in VERB_FEATURE_VALUES+LEXICAL_FEATURE_VALUES+['gloss']
    }

    predicted_forms = inflect_word(
        root=root,
        features=verb_filtered,
    )

    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_forms(gold_adj):
    root = gold_adj.pop('root')
    form = gold_adj.pop('form')
    gold_adj["part_of_speech"]='adjective'

    predicted_forms = inflect_word(root, features=gold_adj)
    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_parsing(gold_adj):
    analyzed_form = gold_adj['form']
    gold_adj['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_adj['form']=form

    predicted_parse = parse_word(form)[0]
    gold_adj_filtered = {
        k: v for k,v in gold_adj.items()
        if k in predicted_parse
    }
    assert predicted_parse == gold_adj_filtered

@pytest.mark.parametrize("gold_word", get_uninflected_word_data())
def test_uninflected_forms(gold_word):
    word = gold_word['word']
    pos = gold_word['part_of_speech']
    gloss = gold_word['gloss']

    parses = parse_word(word)[0]
    assert parsed['part_of_speech'] == pos
    assert parsed['gloss'] == gloss

@pytest.mark.parametrize("aux", get_gold_auxs())
def test_gold_auxs(aux):
    form = aux.pop('form')

    aux_filtered = {
        k: v for k,v in aux.items()
        if k in VERB_FEATURE_VALUES or k=='gloss'
    }
    predicted_forms = inflect_word('', features=aux_filtered)

    assert form in predicted_forms