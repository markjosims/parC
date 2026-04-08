"""
Defines two principal classes: `Registry` and `Orchestrator`.
`Registry` stores all the data associated with a particular type
of YAML config. `Orchestrator` sits over `Registry` and manages
all configs for a particular area of the grammar.

Grammars is initialized in two primary stages: reading and loading.
'Reading' refers to reading YAML files into Python dictionaries, but
not interpreting or acting on the data in any way. The `Grammar` class
(the Orchestrator of Orchestrators) handles all reading logic, and passes
YAML data to child Orchestrator classes, which in turn pass data onto
child Registries.

The 'loading' phase is where YAML data is interpreted into actionable logic,
e.g. the phones from an inventory config are built into FSTs.
'loading' is shared between orchestrators and registries, and the steps involved
differ greatly based on the area of grammar concerned.
"""

import os
import yaml
from pathlib import Path
import unicodedata
from jsonschema import validate, ValidationError
from src.config_utils import load_schema
from loguru import logger

class ConfigWalkerMixin:
    """
    Provides logic for reading and validating YAML files.
    """

    def read_config_files(self, kind: str) -> dict[str, str]:
        """
        Load all `config` files for the specified kind within `config_dir`
        into a dict mapping filename to data.
        """
        config_objects = {}
        for filename in self.glob_config_files():
            with open(filename, "r") as f:
                content = f.read()
                content_norm = unicodedata.normalize("NFKD", content)
                config_data = yaml.safe_load(content_norm)

                # store filepath for config
                config_data["source_path"] = str(filename)
                if config_data.get("kind") == self.kind:
                    try:
                        validate(instance=config_data, schema=self.schema)
                        config_objects[str(filename)] = config_data
                    except ValidationError as e:
                        logger.exception(f"Invalid config file {filename}: {e}")
                        raise ValidationError(f"Invalid config file {filename}: {e}")
        return config_data

    def glob_config_files(self):
        return self.config_dir.glob(f"**/*.yaml")

    def find_config_file(self, name: str) -> Path:
        """Search all config subdirectories for <name>.yaml."""
        for filename in self.glob_config_files(name):
            if Path(filename).stem == name:
                return Path(filename)
        raise FileNotFoundError(
            f"Config file '{name}.yaml' not found in any config subdirectory."
        )

    def resolve_ref(self, name: str) -> dict:
        """
        Resolve a $name cross-file reference.

        Strips the leading '$', searches all config subdirectories for
        <name>.yaml, and returns the raw (un-resolved) YAML dict.
        """
        if name.startswith("$"):
            name = name[1:]
        path = self.find_config_file(name)
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _resolve_values(self, obj) -> dict:
        """
        Recursively walk a deserialized YAML structure.
        Any string value starting with '$' is replaced by the fully-resolved
        content of the referenced config file.
        """
        if isinstance(obj, str):
            if obj.startswith("$"):
                ref_dict = self.resolve_ref(obj)
                return self._resolve_values(ref_dict)
            return obj
        elif isinstance(obj, list):
            return [self._resolve_values(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._resolve_values(value) for key, value in obj.items()}
        else:
            return obj

    def load_config(self, path: Path | str) -> dict:
        """
        Load a YAML config file and recursively resolve all $name references.

        Arguments:
            path: Path to the YAML config file.
        Returns:
            Fully-resolved config dict.
        """
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return self._resolve_values(raw)

class Orchestrator:
    ...

class Registry:
    def __init__(
        self,
        kind: str,
        data: dict | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.kind = kind
        self.schema = load_schema(kind)

        if data is None and config_objects is None:
            self.data = {}
            self.config_objects = {}
        elif data is not None and config_objects is None:
            self.data = data
            self.config_objects = {}
        elif data is None and config_objects is not None:
            self.config_objects = config_objects
            self.data = self.load_all_configs()
        else:
            raise ValueError("Cannot specify both data and config_list")

    def load_all_configs(self) -> dict:
        raise NotImplementedError(
            "Must be implemented by subclass to load and merge all configs in config_list."
        )

    def load_data_from_config(self) -> dict:
        raise NotImplementedError(
            "Must be implemented by subclass to load data from a single config dict."
        )


class ReservedSymbolMixin:
    """
    Mixin class for registries to define reserved symbols that cannot be used as
    inventory item values. This is to prevent collisions between user-defined
    inventory items and special symbols used in pattern/rule contexts.
    """

    bow = "[BOW]"
    eow = "[EOW]"
    insert = "[INSERT]"
    substitute = "[SUBSTITUTE]"
    delete = "[DELETE]"

    word_edge = "#"
    phone_ref = "<Phone>"
    flag_ref = "<Flag>"
    sigma_ref = "<Sigma>"
    dot = "."
    epsilon_ref = "<Empty>"
    boundary_ref = "<Boundary>"

    affix_boundary = "-"
    clitic_boundary = "="
    periphrasis_break = "_"

    star = "*"
    plus = "+"
    optional = "?"
    union = "|"
    caret = "^"
    left_paren = "("
    right_paren = ")"
    # curly braces indicate union of tokens, e.g. {A B} matches either A or B
    # similar to square brackets in regex
    left_brace = "{"
    right_brace = "}"

    left_delimiters = (left_paren, left_brace)
    right_delimiters = (right_paren, right_brace)
    unary_operators = (star, plus, optional)
    pipe_operator = union  # (for now) pipe operator is only binary operator
    caret_operator = caret  # for negation in braced expressions
    reserved_refs = (phone_ref, flag_ref, epsilon_ref, dot, sigma_ref, boundary_ref)
    bow_eow_flags = (bow, eow)
    edit_flags = (insert, substitute, delete)
    boundary_symbols = (affix_boundary, clitic_boundary, periphrasis_break)

    reserved_symbols = (
        left_delimiters
        + right_delimiters
        + unary_operators
        + (pipe_operator,)
        + reserved_refs
        + bow_eow_flags
        + boundary_symbols
    )
