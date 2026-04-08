import yaml
from pathlib import Path
import unicodedata
from jsonschema import validate, ValidationError
from loguru import logger
from src.config_utils.schema_validation import load_schema, CONFIG_KINDS
from camel_converter import to_snake


class ConfigWalker:
    """
    Provides logic for reading and validating YAML files.
    """

    def __init__(self, config_dir: str | Path) -> "ConfigWalker":
        self.config_dir = Path(config_dir)

    def get_all_config_files(
        self, use_snake_case: bool = True
    ) -> dict[str, list[dict]]:
        """
        Reads all YAML data in the config folder and returns
        as dict mapping config type to list of objects.
        """
        config_map = {}
        for kind in CONFIG_KINDS:
            kind_name = kind
            if use_snake_case:
                kind_name = to_snake(kind)
            configs = self.read_config_files(kind)
            config_map[kind_name] = configs
        return config_map

    def read_config_files(self, kind: str) -> dict[str, str]:
        """
        Load all `config` files for the specified kind within `config_dir`
        into a dict mapping filename to data.
        """
        schema = load_schema(kind)
        config_objects = {}
        for filename in self.glob_config_files():
            with open(filename, "r") as f:
                content = f.read()
                content_norm = unicodedata.normalize("NFKD", content)
                config_data = yaml.safe_load(content_norm)

                # store filepath for config
                config_data["source_path"] = str(filename)
                if config_data.get("kind") == kind:
                    try:
                        validate(instance=config_data, schema=schema)
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
