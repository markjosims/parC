import os
from collections import Counter
from typing import Sequence

import numpy as np
import pandas as pd
from frozendict import frozendict

from src.constants import MAX_HOMOPHONE_COUNT
from src.diagnostics import build_diagnostic_error
from src.models import (
    FEATURE_STRING_RE,
    HOMOPHONE_INDEX_FEATURE,
    INFLECTED_WORD_RE,
    FeatureSet,
    InflectedWord,
    Lexeme,
    ParadigmFile,
    PartOfSpeechFile,
    Project,
)
from src.yaml.yaml_server import kind_dir


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
    gloss = lexeme_row.gloss
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
        gloss=gloss,
        homophone_index=homophone_index or 0,
        principal_parts=principal_parts,
        lexical_features=FeatureSet(**lexical_features),
    )


def convert_lexeme_table_to_lexemes(
    lexeme_table: pd.DataFrame | Sequence[dict[str, str | int]],
    part_of_speech_id: str,
    project: Project,
) -> tuple[Lexeme, ...]:
    if type(lexeme_table) is not pd.DataFrame:
        lexeme_table = pd.DataFrame(lexeme_table)

    roots = lexeme_table.root.tolist()
    glosses = lexeme_table.gloss.tolist()
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
            gloss=gloss,
            homophone_index=homophone_index,
            principal_parts=principal_parts,
            lexical_features=lexical_features,
        )
        for root, gloss, homophone_index, principal_parts, lexical_features in zip(
            roots,
            glosses,
            homophone_indices,
            principal_part_array,
            lexical_feature_array,
        )
    )
    return lexemes


def inflected_word_from_string(
    inflected_string: str,
    project: Project,
) -> InflectedWord:
    match = INFLECTED_WORD_RE.match(inflected_string)
    paradigm_id = match.group("paradigm_id")
    lexical_feature_str = match.group("lexical_features")
    lexical_features = dict(FEATURE_STRING_RE.findall(lexical_feature_str))
    inflectional_feature_str = match.group("inflectional_features")
    inflectional_features = dict(FEATURE_STRING_RE.findall(inflectional_feature_str))
    root = match.group("root")
    homophone_index = lexical_features.pop(HOMOPHONE_INDEX_FEATURE)
    paradigm: ParadigmFile = project.struct_registry["ParadigmFile"][paradigm_id]
    part_of_speech_id = paradigm.part_of_speech
    lexeme = retrieve_lexeme(
        root=root,
        part_of_speech_id=part_of_speech_id,
        project=project,
        homophone_index=homophone_index,
    )
    if not lexeme.lexical_features == FeatureSet(**lexical_features):
        raise build_diagnostic_error(
            message=f"Expected parsed lexical features {FeatureSet(**lexical_features)} to match retrieved {lexeme.lexical_features} for root {root}"
        )
    return InflectedWord(
        paradigm_id=paradigm_id,
        inflectional_features=FeatureSet(**inflectional_features),
        lexeme=lexeme,
    )
