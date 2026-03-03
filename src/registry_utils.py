import os
import yaml
from pathlib import Path
from glob import glob
from typing import Union
from jsonschema import validate, ValidationError
from src.config_utils import load_schema
from loguru import logger

class Registry:
    def __init__(self, kind: str, config_dir: os.PathLike): 
        self.kind = kind
        self.schema = load_schema(kind)
        self.config_dir = Path(config_dir)
        self.config_list = self.load_config_files()

    def load_config_files(self) -> dict:
        """
        Load all `config` files for the specified kind within `config_dir`.
        """
        config_list = []
        for filename in self._glob_config_files():
            with open(filename, 'r') as f:
                config_data = yaml.safe_load(f)
                if config_data.get('kind') == self.kind:
                    try:
                        validate(instance=config_data, schema=self.schema)
                        config_list.append(config_data)
                    except ValidationError as e:
                        logger.error(f"Invalid config file {filename}: {e}")
        return config_list


    def _glob_config_files(self, name: str='*'):
        return self.config_dir.glob(f'**/{name}.yaml')

    def _find_config_file(self, name: str) -> Path:
        """Search all config subdirectories for <name>.yaml."""
        for filename in self._glob_config_files(name):
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
        path = self._find_config_file(name)
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


    def load_config(self, path: Union[Path, str]) -> dict:
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
