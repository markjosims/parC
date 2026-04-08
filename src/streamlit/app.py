import streamlit as st
from src.streamlit.state.watcher import start_watcher
from src.streamlit.state.config_paths import get_config_dir
from src.streamlit.state.registry_loader import load_registry
from src.grammar import Grammar

from src.streamlit.pages.inventory import inventory_page

GRAMMAR_REGISTRY_CACHE: dict[str, tuple[float, Grammar]] = {}
GRAMMAR_BUILD_STATUS: dict[tuple[str, str], dict] = {}


def initialize_state():
    """
    Loads directory watcher and GrammarRegistry.
    """
    config_dir = get_config_dir()
    st.session_state["config_dir"] = config_dir
    st.session_state["watcher"] = start_watcher(
        config_dir=config_dir, cache=GRAMMAR_REGISTRY_CACHE
    )

def navbar():
    pages = {
        "Home": [st.Page(home_page, title="Home")],
        "Edit grammar": [
            st.Page(inventory_page, title="Inventory"),
        ],
        "Inflect": [],
        "Parse": [],
        "Corpus": [],
    }
    return st.navigation(pages, position="top")

def home_page():
    st.header("Home page")

def main():
    initialize_state()
    pages = navbar()
    pages.run()

if __name__ == "__main__":
    main()
