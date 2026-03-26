from pandas._config import config
import streamlit as st
import pandas as pd
import os
from src.registry.grammar_registry import GrammarRegistry

# First try loading config dir from session state, then environment
# If neither is defined, prompt user to input
config_dir = getattr(st.session_state, "config_dir", None)

if config_dir is None:
    config_dir = os.environ.get("M2_CONFIG_DIR", None)
    config_dir = os.path.expanduser(config_dir)

if config_dir is None:
    config_dir = st.text_input(
        "Parser folder:", value="/path/to/folder/", key="config_dir"
    )
else:
    try:
        grammar_reg = GrammarRegistry.from_config_dir(config_dir)
        st.write("Loaded parser config from", config_dir)
        st.write(f"Detected {len(grammar_reg.paradigms)} paradigms")
    except Exception as e:
        st.write(f"Error loading parser from {config_dir}: {e}")

csv = st.file_uploader(
    label="Upload spreadsheet with sentences",
    type=["csv", "xlsx"],
)

# using default path for development, remove later
csv = csv or "/home/markjos/projects/parser_tira/data/sentences/sentences.csv"

if csv is not None:
    df = pd.read_csv(csv)
    event = st.dataframe(df, selection_mode="single-cell", on_select="rerun")

    if event.selection.cells:
        row, col = event.selection.cells[0]
        row = int(row)
        st.write(row, col)
        value = df.iloc[row][col]
        words = value.split()
        st.write(value)
        st.pills("Parse input:", options=words, key="selected_word")
        st.pills(
            "Paradigm:", options=grammar_reg.paradigms.keys(), key="selected_paradigm"
        )
        st.checkbox("Inexact search:", key="inexact_search")

    selected_word = getattr(st.session_state, "selected_word", None)
    selected_paradigm = getattr(st.session_state, "selected_paradigm", None)
    if selected_word is not None and selected_paradigm is not None:
        paradigm = grammar_reg.paradigms[selected_paradigm]
        inexact_search = getattr(st.session_state, "inexact_search", None)
        if inexact_search:
            parse_output = paradigm.search_parses(selected_word)
        else:
            parse_output = paradigm.get_parses(selected_word)
        st.session_state.parse_output = parse_output

    parse_output = getattr(st.session_state, "parse_output", None)
    if parse_output is not None:
        parse_df = pd.DataFrame(parse_output)
        parse_event = st.dataframe(
            parse_df, selection_mode="single-row", on_select="rerun"
        )

        if parse_event.selection.rows:
            row_i = parse_event.selection.rows[0]
            form = parse_df.iloc[row_i]["form"]
            if st.button(
                f"Select parse {row_i + 1} with form {form} for word {selected_word}"
            ):
                st.write(f"Selected word {row_i + 1}")
