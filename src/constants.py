import os
from pathlib import Path

from dotenv import load_dotenv

# filepaths
PROJECT_ROOT = Path(__file__).parent.parent

SCHEMA_DIR = PROJECT_ROOT / "schemas"


def get_yaml_dir() -> Path:
    load_dotenv(PROJECT_ROOT / "parC.env")
    return Path(os.environ.get("YAML_DIR")) or PROJECT_ROOT / "yaml" / "spanish-example"


def set_yaml_dir(path: str):
    # TODO: add UI for changing YAML_DIR
    os.environ["YAML_DIR"] = path


MAX_HOMOPHONE_COUNT = 10


# pynini constants


# copied from https://github.com/kylebgorman/pynini/blob/27ce19048193358cd362a4de6b157cb43ab6e2eb/extensions/stringcompile.h#L69
# a bit hacky: since ... TODO check if we really need to include EOS/BOS in symbol table
BOS_INDEX = 0xF8FE
EOS_INDEX = 0xF8FF
