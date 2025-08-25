"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms

TIRA_CONSONANTS = [
    'm', 'n',      'ɲ', 'ŋ',
    'p', 't̪', 't', 'c', 'k',
    'b', 'd̪', 'd', 'ɟ', 'g',
              's',
    'v', 'ð',
    'w',      'l'  'j',
         'r', 'ɾ', 'ɽ',
]

TIRA_VOWELS = [
    'i',      'u',
    'ɪ',      'ʊ',
    'e', 'ə', 'o',
    'ɛ', 'ɜ', 'ɔ',
         'a',
]

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'
TIRA_TONES = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONES:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

C = pynini.union(*TIRA_CONSONANTS).optimize()
V = pynini.union(*TIRA_VOWELS).optimize()
T = pynini.union(*TIRA_TONES).optimize()
SIGMASTAR = pynini.union(C,V,T).closure().optimize()
STEM = paradigms.make_byte_star_except_boundary()
