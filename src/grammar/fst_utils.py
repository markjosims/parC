import re

import pynini
from frozendict import frozendict


def is_acceptor(fsa: pynini.Fst) -> bool:
    if not isinstance(fsa, pynini.Fst):
        raise ValueError(f"Expected pynini.Fst but got {fsa} for fsa arg.")
    return fsa.properties(pynini.ACCEPTOR, True)


def stringify_features(
    feature_values: set[tuple[str, str]] | dict[str, str] | frozendict[str, str],
) -> str:
    if isinstance(feature_values, (dict, frozendict)):
        feature_values = list(feature_values.items())
    return "".join(f"[{f}={v}]" for f, v in sorted(feature_values))


def feature_dict_to_tuple(
    feature_values: dict[str, str] | frozendict[str, str],
) -> str:
    return tuple((key, value) for key, value in sorted(feature_values.items()))


def serialize_feature_str(feature_str: str) -> dict[str, str]:
    return dict(re.findall(r"\[([a-z]+)=([a-z]+)\]"), feature_str)
