import pynini
from pynini.lib.edit_transducer import (
    EditTransducer,
    DEFAULT_INSERT_COST,
    DEFAULT_SUBSTITUTE_COST,
    DEFAULT_DELETE_COST
)

INSERT = EditTransducer.INSERT
DELETE = EditTransducer.DELETE
SUBSTITUTE = EditTransducer.SUBSTITUTE

def get_searchable_lexicon(
        lexicon,
        insertions,
        substitutions,
        deletions,
        sigma,
        insert_cost=DEFAULT_INSERT_COST,
        sub_cost=DEFAULT_SUBSTITUTE_COST,
        delete_cost=DEFAULT_DELETE_COST,
    ):
    ...

def get_edit_factors(
        insertions,
        substitutions,
        deletions,
        sigma,
        insert_cost=DEFAULT_INSERT_COST,
        sub_cost=DEFAULT_SUBSTITUTE_COST,
        delete_cost=DEFAULT_DELETE_COST,
    ):
    insert_graph = _get_insertion_graph(insertions, insert_cost, sigma)
    delete_graph = _get_deletion_graph(deletions, delete_cost, sigma)
    sub_graph = _get_substitution_graph(substitutions, sub_cost, sigma)

    edit_graph = pynini.union(insert_graph, delete_graph, sub_graph).optimize()

    left_factor = edit_graph.union(sigma).closure().optimize()
    right_factor = pynini.invert(left_factor)
    generated_symbols = pynini.generated_symbols()
    insert_label = generated_symbols.find(INSERT)
    delete_label = generated_symbols.find(DELETE)
    pairs = [(insert_label, delete_label), (delete_label, insert_label)]
    right_factor = right_factor.relabel_pairs(ipairs=pairs)
    return left_factor, right_factor

def _get_insertion_graph(insertions, insert_cost, sigma) -> pynini.Fst:
    insert_graph = pynini.cross(sigma, pynini.accep(INSERT, insert_cost))
    return insert_graph
    # insert_inputs = pynini.union(insert[0] for insert in insertions)
    # sigma_except_inserts = sigma-insert_inputs

def _get_deletion_graph(deletions, delete_cost, sigma) -> pynini.Fst:
    delete_graph = pynini.cross(sigma, pynini.accep(DELETE, delete_cost))
    return delete_graph
    
def _get_substitution_graph(substitutions, sub_cost, sigma) -> pynini.Fst:
    sub_graph = pynini.cross(sigma, pynini.accep(DELETE, sub_cost))
    return sub_graph

def get_matches(query, left_factor, lexicon):
    ...