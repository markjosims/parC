import os
from collections import Counter

import numpy as np
import pandas as pd
from frozendict import frozendict

from src.constants import MAX_HOMOPHONE_COUNT
from src.fst_utils import stringify_features
from src.models import PartOfSpeechFile, Project
from src.yaml.yaml_server import kind_dir


def get_lexicon_path(part_of_speech_id: str) -> str:
    return os.path.join(
        kind_dir("Wordlists"),
        f"{part_of_speech_id}.csv",
    )


def load_lexicon_df(part_of_speech_id: str) -> pd.DataFrame:
    df = pd.read_csv(
        get_lexicon_path(part_of_speech_id),
        keep_default_na=False,
    )
    df["homophone_index"] = get_homophone_indices(df)
    return df


def init_lexicon(
    part_of_speech_id: str,
    project: Project,
) -> None:
    part_of_speech: PartOfSpeechFile = project.struct_registry["PartOfSpeech"][
        part_of_speech_id
    ]
    df = pd.DataFrame(
        columns=["root", "gloss"]
        + part_of_speech.lexical_features
        + part_of_speech.principal_parts
    )
    lexicon_path = get_lexicon_path(part_of_speech_id)
    os.makedirs(os.path.dirname(lexicon_path), exist_ok=True)
    df.to_csv(lexicon_path, index=False)


def get_homophone_indices(df: pd.DataFrame) -> pd.Series[int]:
    homophone_counter = Counter()
    homophone_indices = []
    for root in df["root"].tolist():
        if homophone_counter[root] > MAX_HOMOPHONE_COUNT:
            raise ValueError("Maximum number of homophones exceeded.")
        homophone_indices.append(homophone_counter[root])
        homophone_counter[root] += 1
    return pd.Series(homophone_indices)


def filter_lexicon_by_features(
    lexicon_basename: str,
    lexical_features: set[tuple[str, str]] | dict[str, str],
) -> pd.DataFrame:
    if isinstance(lexical_features, (dict, frozendict)):
        lexical_features = set(lexical_features.items())
    df = load_lexicon_df(lexicon_basename)
    filter = pd.Series([True] * len(df), index=df.index)
    for feature, value in lexical_features:
        filter &= df[feature] == value

    filtered_df = df[filter]
    return filtered_df


def get_principal_part_for_all_roots(
    lexicon_basename: str, principal_part: str, fallback_to_root: bool = True
) -> list[str]:
    df = load_lexicon_df(lexicon_basename)
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


def stringify_lexicon_row(
    row: dict[str, str | int] or pd.Series,
    feature_cols: list[str],
) -> str:
    features = {k: v for k, v in row.items() if k != "root"}
    root = row["root"]
    lexeme_str = f"{root}{stringify_features(features)}"
    return lexeme_str


def stringify_lexemes(
    lexemes: pd.DataFrame | list[dict[str, str | int]],
    part_of_speech_id: str,
    project: Project,
) -> tuple[str, ...]:
    if type(lexemes) is not pd.DataFrame:
        lexemes = pd.DataFrame(lexemes)
    part_of_speech = project.struct_registry["PartOfSpeech"][part_of_speech_id]
    lexical_features = part_of_speech.lexical_features
    lexical_features += "homophone_index"
    lexeme_strs = lexemes.apply(
        lambda row: stringify_lexicon_row(row, feature_cols=lexical_features),
        axis=1,
    ).tolist()
    return lexeme_strs
