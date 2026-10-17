import os
from collections import Counter
from typing import Sequence

import numpy as np
import pandas as pd
from frozendict import frozendict

from src.constants import MAX_HOMOPHONE_COUNT
from src.grammar.fst_utils import pad_with_word_edge_tags, stringify_features
from src.models import FeatureSet, Lexeme, PartOfSpeechFile, Project
from src.yaml.yaml_server import kind_dir

HOMOPHONE_INDEX_FEATURE = "homophone_index"


def get_lexicon_path(part_of_speech_id: str) -> str:
    return os.path.join(
        kind_dir("Wordlist"),
        f"{part_of_speech_id}.csv",
    )


def load_lexeme_table(part_of_speech_id: str) -> pd.DataFrame:
    lexeme_table = pd.read_csv(
        get_lexicon_path(part_of_speech_id),
        keep_default_na=False,
    )
    lexeme_table[HOMOPHONE_INDEX_FEATURE] = get_homophone_indices(lexeme_table)
    return lexeme_table


def init_lexicon(
    part_of_speech_id: str,
    project: Project,
) -> None:
    part_of_speech: PartOfSpeechFile = project.struct_registry["PartOfSpeech"][
        part_of_speech_id
    ]
    lexeme_table = pd.DataFrame(
        columns=["root", "gloss"]
        + part_of_speech.lexical_features
        + part_of_speech.principal_parts
    )
    lexicon_path = get_lexicon_path(part_of_speech_id)
    os.makedirs(os.path.dirname(lexicon_path), exist_ok=True)
    lexeme_table.to_csv(lexicon_path, index=False)


def get_homophone_indices(lexeme_table: pd.DataFrame) -> pd.Series:
    homophone_counter = Counter()
    homophone_indices = []
    for root in lexeme_table["root"].tolist():
        if homophone_counter[root] > MAX_HOMOPHONE_COUNT:
            raise ValueError("Maximum number of homophones exceeded.")
        homophone_indices.append(homophone_counter[root])
        homophone_counter[root] += 1
    return pd.Series(homophone_indices)


def filter_lexicon_by_features(
    lexicon_basename: str,
    lexical_features: Sequence[tuple[str, str]] | dict[str, str],
) -> pd.DataFrame:
    if isinstance(lexical_features, (dict, frozendict)):
        lexical_features = set(lexical_features.items())
    df = load_lexeme_table(lexicon_basename)
    feature_filter = pd.Series([True] * len(df), index=df.index)
    for feature, value in lexical_features:
        feature_filter &= df[feature] == value

    filtered_df = df[feature_filter]
    return filtered_df


def get_principal_part_for_all_roots(
    lexicon_basename: str,
    principal_part: str,
    fallback_to_root: bool = True,
) -> list[str]:
    df = load_lexeme_table(lexicon_basename)
    if fallback_to_root:
        return (
            df[principal_part]
            .replace(
                "",
                np.nan,
            )
            .fillna(df["root"])
            .tolist()
        )
    return df[principal_part].tolist()


def _stringify_lexeme_row(
    row: dict[str, str | int] or pd.Series,
    feature_cols: list[str],
    lexeme_col: str = "root",
    fallback_to_root: bool = True,
) -> str:
    features = {k: v for k, v in row.items() if k in feature_cols}
    stem = row[lexeme_col]
    if not stem and fallback_to_root:
        stem = row["root"]
    padded_stem = pad_with_word_edge_tags(stem)
    lexeme_str = f"{padded_stem}{stringify_features(features)}"
    return lexeme_str


def stringify_lexeme_table(
    lexeme_table: pd.DataFrame | list[dict[str, str | int]],
    part_of_speech_id: str,
    project: Project,
    lexeme_col: str = "root",
    fallback_to_root: bool = True,
) -> pd.Series:
    if type(lexeme_table) is not pd.DataFrame:
        lexeme_table = pd.DataFrame(lexeme_table)
    part_of_speech = project.struct_registry["PartOfSpeechFile"][part_of_speech_id]
    lexical_features = part_of_speech.lexical_features
    lexical_features += (HOMOPHONE_INDEX_FEATURE,)
    lexeme_strs = lexeme_table.apply(
        lambda row: _stringify_lexeme_row(
            row,
            feature_cols=lexical_features,
            lexeme_col=lexeme_col,
            fallback_to_root=fallback_to_root,
        ),
        axis=1,
    )
    return lexeme_strs


def retrieve_lexeme_row(
    root: str,
    lexeme_table: pd.DataFrame | list[dict[str, str | int]],
    homophone_index: int | None = None,
) -> pd.Series:
    if type(lexeme_table) is not pd.DataFrame:
        lexeme_table = pd.DataFrame(lexeme_table)

    root_mask = lexeme_table.root == root
    if root_mask.sum() == 0:
        raise KeyError(f"Root {root} not found in lexicon")
    if root_mask.sum() == 1:
        return lexeme_table[root_mask].iloc[0]
    if homophone_index is None:
        raise ValueError(
            f"Multiple roots with form {root} found in lexicon, pass homophone_index"
        )
    homophone_mask = root_mask & (lexeme_table.homophone_index == homophone_index)
    if homophone_mask.sum() == 0:
        raise KeyError(f"No root {root} with {homophone_index=}")
    if homophone_mask.sum() > 1:
        raise KeyError(f"Root {root} has multiple rows with {homophone_index=}")
    return lexeme_table[homophone_mask].iloc[0]


def retrieve_lexeme(
    root: str,
    part_of_speech_id: str,
    project: Project,
    homophone_index: int | None = None,
) -> Lexeme:
    lexeme_table = load_lexeme_table(part_of_speech_id=part_of_speech_id)
    lexeme_row = retrieve_lexeme_row(root, lexeme_table, homophone_index)
    part_of_speech: PartOfSpeechFile = project.struct_registry["PartOfSpeechFile"][
        part_of_speech_id
    ]
    principal_parts = {}
    for current_part in part_of_speech.principal_parts:
        principal_parts[current_part] = lexeme_row[current_part]
    lexical_features = {}
    for current_feature in part_of_speech.lexical_features:
        lexical_features[current_feature] = lexeme_row[current_feature]

    return Lexeme(
        root=root,
        homophone_index=homophone_index or 0,
        principal_parts=principal_parts,
        lexical_features=lexical_features,
    )


def convert_lexeme_table_to_lexemes(
    lexeme_table: pd.DataFrame | Sequence[dict[str, str | int]],
    part_of_speech_id: str,
    project: Project,
) -> tuple[Lexeme, ...]:
    if type(lexeme_table) is not pd.DataFrame:
        lexeme_table = pd.DataFrame(lexeme_table)

    roots = lexeme_table.root.tolist()
    homophone_indices = lexeme_table.homophone_index.tolist()

    part_of_speech: PartOfSpeechFile = project.struct_registry["PartOfSpeechFile"][
        part_of_speech_id
    ]
    principal_part_array = lexeme_table[list(part_of_speech.principal_parts)].to_dict(
        orient="records"
    )
    lexical_feature_array = [
        FeatureSet(**row)
        for row in lexeme_table[list(part_of_speech.lexical_features)].to_dict(
            orient="records"
        )
    ]
    lexemes = tuple(
        Lexeme(
            root=root,
            homophone_index=homophone_index,
            principal_parts=principal_parts,
            lexical_features=lexical_features,
        )
        for root, homophone_index, principal_parts, lexical_features in zip(
            roots,
            homophone_indices,
            principal_part_array,
            lexical_feature_array,
        )
    )
    return lexemes
