"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms, pynutil, rewrite
from typing import *
import pydot
import os


DENTAL_T = 't̪'
DENTAL_D = 'd̪'

TIRA_STOPS = [
    'p', DENTAL_T, 't', 'c', 'k',
    'b', DENTAL_D, 'd', 'ɟ', 'g',
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

HIGH_TONE_SYMBOL = '<H>'
LOW_TONE_SYMBOL = '<L>'
FALL_TONE_SYMBOL = '<HL>'
RISE_TONE_SYMBOL = '<LH>'

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'

SYMBOL2DIAC = {
    HIGH_TONE_SYMBOL: HIGH_TONE,
    LOW_TONE_SYMBOL: LOW_TONE,
    FALL_TONE_SYMBOL: FALL_TONE,
    RISE_TONE_SYMBOL: RISE_TONE,
}
DIAC2SYMBOL = {value:key for key, value in SYMBOL2DIAC.items()}


TIRA_TONE_SYMBOLS = [HIGH_TONE_SYMBOL, LOW_TONE_SYMBOL, FALL_TONE_SYMBOL, RISE_TONE_SYMBOL]
TIRA_TONE_DIACS = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

PLACEHOLDER_TBU_STR = 'x'
BOUNDARY_STR = '-'
WORD_BOUNDARY_STR = '|'
EPSILON_SYMBOL = '<eps>'

SPECIAL_SYMBOLS = [BOUNDARY_STR, WORD_BOUNDARY_STR, PLACEHOLDER_TBU_STR]

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
TIRA_SYMBOL_TABLE.add_symbol(EPSILON_SYMBOL)
for symbol in SPECIAL_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(symbol)
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONE_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

# symbol table wrappers

def set_symbols(fst: pynini.Fst) -> pynini.Fst:
    fst.set_input_symbols(TIRA_SYMBOL_TABLE)
    fst.set_output_symbols(TIRA_SYMBOL_TABLE)
    return fst

def tone2diac(tone_str: str) -> str:
    for tone_symbol, tone_diac in SYMBOL2DIAC.items():
        tone_str = tone_str.replace(tone_symbol, tone_diac)
    return tone_str

def tone2symbol(tone_str: str) -> str:
    for tone_diac, tone_symbol in DIAC2SYMBOL.items():
        tone_str = tone_str.replace(tone_diac, tone_symbol)
    return tone_str

def collapse_dental_bridge(encoded_string: str) -> str:
    for dental_consonant in DENTAL_T, DENTAL_D:
        expanded_dental_consonant = ' '.join(dental_consonant)
        encoded_string = encoded_string.replace(expanded_dental_consonant, dental_consonant)
    return encoded_string

def encode_fst_string(input_string: Union[str, Sequence[str]]) -> Union[str, List[str]]:
    """
    Replace all word boundaries with the `WORD_BOUNDARY_STR` symbol (default "|"),
    separates all characters with spaces, and replaces tone diacritics with
    dedicated symbols.
    """
    if type(input_string) is not str:
        return [encode_fst_string(input_element) for input_element in input_string]
    str_w_word_boundaries = input_string.replace(' ', WORD_BOUNDARY_STR)
    tokenized_str = " ".join(str_w_word_boundaries)
    str_w_tone_symbols = tone2symbol(tokenized_str)
    str_w_collapsed_dentals = collapse_dental_bridge(str_w_tone_symbols)
    return str_w_collapsed_dentals

def decode_fst_string(
        input_string: Union[str, Sequence[str], pynini.Fst]
    ) -> Union[str, List[str]]:
    """
    Condense all separated characters, replaces `WORD_BOUNDARY_STR` symbol (default "|")
    with a space, and changes tone symbols back to diacritics.
    If `input_string` is an FST, call `Fst.string()` first.
    """
    if type(input_string) is pynini.Fst:
        input_string = input_string.string(token_type=TIRA_SYMBOL_TABLE)
    elif type(input_string) is not str:
        return [decode_fst_string(input_element) for input_element in input_string]
    detokenized_str = input_string.replace(' ', '')
    str_w_word_spaces = detokenized_str.replace(WORD_BOUNDARY_STR, ' ')
    str_w_tone_diacs = tone2diac(str_w_word_spaces)
    return str_w_tone_diacs

def fst(
        fst_input: Union[str, Sequence[str]],
        fst_output: Union[str, Sequence[str], None] = None,
        weight: pynini.WeightLike = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  String or list of strings to be accepted by the FST
        fst_output: (Optional) string or list of strings to be output by the FST
        weight:     (Optional) weight value for FST
    Returns:
        f:          Finite State Transducer
    
    FST factory used to automatically set `TIRA_SYMBOL_TABLE`.
    Input and output may be string or list of strings. If only input is passed,
    returns an FSA over the input string or unin of strings. If output is passed,
    return an FST transducing input to output.
    """
    if type(fst_input) is str:
        f = pynini.accep(encode_fst_string(fst_input), token_type=TIRA_SYMBOL_TABLE, weight=weight)
    else:
        f = pynini.union(*[fst(fst_element) for fst_element in fst_input])
    
    if fst_output is None:
        # no output, just return acceptor
        f = set_symbols(f)
        f.optimize()
        return f
    
    # create acceptor for output
    output_fsa = fst(fst_input=fst_output, fst_output=None)
    f = pynini.cross(f, output_fsa)
    f = set_symbols(f)
    f.optimize()
    return f

def insert_fst(
        fst_output: Union[str, Sequence[str]],
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_output:  String or list of strings to be output by the FST
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST mapping <eps> to the output string(s)
    
    Wraps `pynutil.insert`, calling `fst` factory on output.
    """
    output_fsa = fst(fst_input=fst_output, weight=weight)
    f = pynutil.insert(output_fsa)
    f = set_symbols(f)
    return f

def delete_fst(
        fst_input: Union[str, Sequence[str]],
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  String or list of strings to be accepted by the FST
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST mapping the input string(s) to <eps>
    
    Wraps `pynutil.delete`, calling `fst` factory on input.
    """
    input_fsa = fst(fst_input=fst_input, weight=weight)
    f = pynutil.delete(input_fsa)
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

BOUNDARY = fst(BOUNDARY_STR)
C = fst(TIRA_CONSONANTS)
V = fst(TIRA_VOWELS)
T = fst(TIRA_TONE_DIACS)
TBU = fst(TIRA_TBUS)
PLACEHOLDER_TBU = fst(PLACEHOLDER_TBU_STR)
SIGMA = C|V|T|BOUNDARY|PLACEHOLDER_TBU
SIGMA_EXCEPT_PLACEHOLDER = C|V|T|BOUNDARY
SIGMASTAR = pynini.closure(SIGMA).optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = pynini.closure(SIGMA_EXCEPT_PLACEHOLDER).optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# phonological processes

ADD_TBU_MARKER = pynini.cdrewrite(
    tau=insert_fst(PLACEHOLDER_TBU_STR),
    l=TBU,
    r=fst(''),
    sigma_star=SIGMASTAR
)
REMOVE_TBU_MARKER_AFTER_ONSET_C = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l=C@TBU,
    r=V,
    sigma_star=SIGMASTAR,
)
REMOVE_TBU_MARKER_AFTER_CODA_C = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l=PLACEHOLDER_TBU+C@TBU,
    r='',
    sigma_star=SIGMASTAR,
)
CLEAN_TBU_MARKERS = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l='',
    r='',
    sigma_star=SIGMASTAR
)

PREPARE_TONE = ADD_TBU_MARKER@REMOVE_TBU_MARKER_AFTER_ONSET_C@REMOVE_TBU_MARKER_AFTER_CODA_C
FINALIZE_TONE = CLEAN_TBU_MARKERS
compose_tone = lambda tone_fst: PREPARE_TONE@tone_fst@FINALIZE_TONE

HTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + insert_fst(HIGH_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()
LTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + insert_fst(LOW_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()

HLSTAR = (HTONE_SYLL + pynini.closure(LTONE_SYLL)).optimize()
ALL_HIGH_TONE = pynini.closure(HTONE_SYLL).optimize()
ALL_LOW_TONE = pynini.closure(LTONE_SYLL).optimize()

HLSTAR_RULE = compose_tone(HLSTAR)
ALL_HIGH_TONE_RULE = compose_tone(ALL_HIGH_TONE)
ALL_LOW_TONE_RULE = compose_tone(ALL_LOW_TONE)

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete(fst("ə")+T),
    l='',
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ADD_PLACEHOLDER_TBU = pynini.cdrewrite(
    tau=insert_fst(PLACEHOLDER_TBU_STR),
    l=C.plus,
    r='[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

FLOAT_TONE_RULE = SIGMASTAR.copy()
for tone in TIRA_TONE_DIACS:
    dock_floating_tone = pynini.cdrewrite(
        tau=insert_fst(tone),
        l=PLACEHOLDER_TBU+tone+pynini.closure(C)+TBU,
        r='',
        sigma_star=SIGMASTAR
    )
    delete_floating_tone = pynini.cdrewrite(
        tau=delete_fst(PLACEHOLDER_TBU_STR+tone),
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