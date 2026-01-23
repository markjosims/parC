from src.parser import parse_word, inflect_word
from src.search import search_word, search_corpus
from src.lexicon import get_gloss_for_root, get_root_for_gloss
from src.fst_helpers import get_gloss_str_from_dict
from functools import wraps

import os
import fire

verbose=os.environ.get('verbose', False)

def parse_printer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return [
            get_gloss_str_from_dict(entry, include_form=True, verbose=False)
            for entry in result
        ]
    return wrapper

def print_list_as_markdown_table(string_list):
    if not string_list:
        print("No results found.")
        return
    # Print header
    print("| Tira | Translation | Gloss |")
    print("|------| ------------|-------|")
    for s in string_list:
        print(f"| {' | '.join(s)} |")

def search_printer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        print_list_as_markdown_table(result)
    return wrapper

if __name__ == "__main__":
    fire.Fire({
        'parse_word': parse_printer(parse_word),
        'inflect_word': inflect_word,
        'search_word': parse_printer(search_word),
        'get_gloss_for_root': get_gloss_for_root,
        'get_root_for_gloss': get_root_for_gloss,
        'search_corpus': search_printer(search_corpus),
    })