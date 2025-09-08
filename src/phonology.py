"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms, pynutil, rewrite
from typing import *
import pydot
import os

TIRA_STOPS = [
    'p', 't̪', 't', 'c', 'k',
    'b', 'd̪', 'd', 'ɟ', 'g',
]
TIRA_FRICATIVES = [
    's', 'v', 'ð',
]
TIRA_GLIDES = [
    'w', 'j',
]
TIRA_NASALS = [
    'm', 'n', 'ɲ', 'ŋ',
]
TIRA_SONORANTS = [
    'l', 'r', 'ɾ', 'ɽ',
]
TIRA_VOWELS = [
    'i',      'u',
    'ɪ',      'ʊ',
    'e', 'ə', 'o',
    'ɛ', 'ɜ', 'ɔ',
         'a',
]

TIRA_CONSONANTS = TIRA_STOPS + TIRA_FRICATIVES + TIRA_GLIDES + TIRA_NASALS + TIRA_SONORANTS

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'
TIRA_TONES = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

PLACEHOLDER_TBU = 'x'
TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

BOUNDARY_STR = '-'
BOUNDARY=pynini.accep(BOUNDARY_STR)

WORD_BOUNDARY = '|'

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
EPSILON_SYMBOL = '<eps>'
TIRA_SYMBOL_TABLE.add_symbol(EPSILON_SYMBOL)
TIRA_SYMBOL_TABLE.add_symbol(WORD_BOUNDARY)
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONES+[BOUNDARY_STR]:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

# symbol table wrappers

def set_symbols(fst: pynini.Fst) -> pynini.Fst:
    fst.set_input_symbols(TIRA_SYMBOL_TABLE)
    fst.set_output_symbols(TIRA_SYMBOL_TABLE)
    return fst

def encode_fst_string(input_string: Union[str, Sequence[str]]) -> Union[str, List[str]]:
    """
    Replace all word boundaries with the `WORD_BOUNDARY` symbol (default "|") and
    separates all characters with spaces.
    """
    if type(input_string) is not str:
        return [encode_fst_string(input_element) for input_element in input_string]
    str_w_word_boundaries = input_string.replace(' ', WORD_BOUNDARY)
    tokenized_str = " ".join(str_w_word_boundaries)
    return tokenized_str

def decode_fst_string(input_string: Union[str, Sequence[str]]) -> Union[str, List[str]]:
    """
    Condense all separated characters and replaces `WORD_BOUNDARY` symbol (default "|")
    with a space.
    """
    if type(input_string) is not str:
        return [decode_fst_string(input_element) for input_element in input_string]
    detokenized_str = input_string.replace(' ', '')
    str_w_word_spaces = detokenized_str.replace(WORD_BOUNDARY, ' ')
    return str_w_word_spaces

def fst(
        fst_input: Union[str, Sequence[str]],
        fst_output: Union[str, Sequence[str], None] = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  String or list of strings to be accepted by the FST
        fst_output: (Optional) string or list of strings to be output by the FST
    Returns:
        f:          Finite State Transducer
    
    FST factory used to automatically set `TIRA_SYMBOL_TABLE`.
    Input and output may be string or list of strings. If only input is passed,
    returns an FSA over the input string or unin of strings. If output is passed,
    return an FST transducing input to output.
    """
    if type(fst_input) is str:
        f = pynini.accep(encode_fst_string(fst_input), token_type=TIRA_SYMBOL_TABLE)
    else:
        f = pynini.union(*[fst(fst_element) for fst_element in fst_input])
    
    if fst_output is None:
        # no output, just return acceptor
        f = set_symbols(f)
        return f
    
    # create acceptor for output
    output_fsa = fst(fst_input=fst_output, fst_output=None)
    f = pynini.cross(f, output_fsa)
    f = set_symbols(f)

    return f

def get_decoded_strings(
        lattice: pynini.Fst,
        project_type: Literal['input', 'output']='output',
        unique_only: bool=True,
    ) -> List[str]:
    """
    Wraps `pynini.lib.rewrite.lattice_to_strings`. Sets `TIRA_SYMBOL_TABLE`
    and calls `decode_fst_string` on output.
    """
    lattice = pynini.project(lattice, project_type=project_type)
    tokenized_strings =  rewrite.lattice_to_strings(lattice, token_type=TIRA_SYMBOL_TABLE)
    decoded_strings = decode_fst_string(tokenized_strings)
    if unique_only:
        return list(set(decoded_strings))
    return decoded_strings

def draw_svg(fst: pynini.Fst, filepath: str = 'tmp.svg', title: Optional[str]=None):
    basename = os.path.basename(filepath)
    dotfile = basename+'.dot'
    fst.draw(
        source=dotfile,
        show_weight_one=True,
        isymbols=fst.input_symbols(),
        osymbols=fst.output_symbols(),
        portrait=True,
        title=title or basename,
    )
    graph = pydot.graph_from_dot_file(dotfile)[0]
    graph.write_svg(filepath)

C = pynini.union(*TIRA_CONSONANTS).optimize()
V = pynini.union(*TIRA_VOWELS).optimize()
T = pynini.union(*TIRA_TONES).optimize()
TBU = pynini.union(*TIRA_TBUS).optimize()
SIGMA = pynini.union(C,V,T,BOUNDARY,PLACEHOLDER_TBU).optimize()
SIGMA_EXCEPT_PLACEHOLDER = pynini.union(C,V,T,BOUNDARY).optimize()
SIGMASTAR = SIGMA.closure().optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = SIGMA_EXCEPT_PLACEHOLDER.closure().optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# phonological processes

ADD_TBU_MARKER = pynini.cdrewrite(
    tau=pynutil.insert(PLACEHOLDER_TBU),
    l=TBU,
    r='',
    sigma_star=SIGMASTAR
)
REMOVE_TBU_MARKER_AFTER_ONSET_C = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l=C@TBU,
    r=V,
    sigma_star=SIGMASTAR,
)
REMOVE_TBU_MARKER_AFTER_CODA_C = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l=PLACEHOLDER_TBU+C@TBU,
    r='',
    sigma_star=SIGMASTAR,
)
CLEAN_TBU_MARKERS = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l='',
    r='',
    sigma_star=SIGMASTAR
)

PREPARE_TONE = ADD_TBU_MARKER@REMOVE_TBU_MARKER_AFTER_ONSET_C@REMOVE_TBU_MARKER_AFTER_CODA_C
FINALIZE_TONE = CLEAN_TBU_MARKERS
compose_tone = lambda tone_fst: PREPARE_TONE@tone_fst@FINALIZE_TONE

HTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + pynutil.insert(HIGH_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()
LTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + pynutil.insert(LOW_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()

HLSTAR = (HTONE_SYLL + LTONE_SYLL.closure()).optimize()
ALL_HIGH_TONE = HTONE_SYLL.closure()
ALL_LOW_TONE = LTONE_SYLL.closure().optimize()

HLSTAR_RULE = compose_tone(HLSTAR)
ALL_HIGH_TONE_RULE = compose_tone(ALL_HIGH_TONE)
ALL_LOW_TONE_RULE = compose_tone(ALL_LOW_TONE)

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete("ə"+T),
    l='',
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ADD_PLACEHOLDER_TBU = pynini.cdrewrite(
    tau=pynutil.insert(PLACEHOLDER_TBU),
    l=C.plus,
    r='[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

FLOAT_TONE_RULE = SIGMASTAR.copy()
for tone in TIRA_TONES:
    dock_floating_tone = pynini.cdrewrite(
        tau=pynutil.insert(tone),
        l=PLACEHOLDER_TBU+tone+C.closure()+TBU,
        r='',
        sigma_star=SIGMASTAR
    )
    delete_floating_tone = pynini.cdrewrite(
        tau=pynutil.delete(PLACEHOLDER_TBU+tone),
        l='',
        r='',
        sigma_star=SIGMASTAR
    )
    rule = dock_floating_tone@delete_floating_tone
    FLOAT_TONE_RULE = FLOAT_TONE_RULE@rule
FLOAT_TONE_RULE = FLOAT_TONE_RULE.optimize()

COMBINE_TONES = pynini.string_map([
    (LOW_TONE+HIGH_TONE, RISE_TONE),
    (HIGH_TONE+LOW_TONE, FALL_TONE),
    (HIGH_TONE+HIGH_TONE, HIGH_TONE),
    (LOW_TONE+LOW_TONE, LOW_TONE),
])
COMBINE_TONES_RULE = pynini.cdrewrite(
    tau=COMBINE_TONES,
    l='',
    r='',
    sigma_star=SIGMASTAR,
)