"""
Implements the `InventoryItem` and `InventoryRegistry` classes.
`InventoryItem` reflects a single node in an inventory tree, and
`InventoryRegistry` aggregates inventory items from across multiple
config files and allows for mapping between `InventoryItems` and their
string representations.
"""

from src.grammar.classes import Registry
from src.fst_utils import Acceptor, ReservedSymbolMixin
from typing import Literal, Optional
from dataclasses import dataclass, field
import os
from loguru import logger


@dataclass
class InventoryItem(Acceptor):
    """
    Represents an item in the inventory, which may be a phone,
    flag or class.
    Attributes:
        value: The string value of the item (e.g. "a", "[TBU]", "<V>").
        type: The type of the item, one of "phone", "flag", or "class".
        children: List of child InventoryItems (for nested structures).
        parent: Optional reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    value: str = ""
    type: Literal["phone", "flag", "class"] = "phone"
    children: list["InventoryItem"] = field(default_factory=list)
    parent: Optional["InventoryItem"] = None
    source: os.PathLike | None = None

    def __post_init__(self):
        super().__post_init__()

        if self.value in ReservedSymbolMixin.reserved_symbols:
            error = f"Inventory item value '{self.value}' is a reserved symbol and cannot be used."
            logger.error(error)
            raise ValueError(error)

        if self.type == "class" and self.children is None:
            raise ValueError("Class items must have children")
        if self.type in ("phone", "flag") and self.children:
            raise ValueError("Phone and flag items cannot have children")

        if (self.type == "class") and (
            not self.value.startswith("<") or not self.value.endswith(">")
        ):
            raise ValueError(
                "Class items must have values that start with '<' and end with '>'"
            )
        if (self.type == "flag") and (
            not self.value.startswith("[") or not self.value.endswith("]")
        ):
            raise ValueError(
                "Flag items must have values that start with '[' and end with ']'"
            )
        if (self.type == "phone") and (
            self.value.startswith("<") or self.value.startswith("[")
        ):
            raise ValueError(
                "Phone items cannot have values that start with '<' or '['"
            )

    @classmethod
    def from_config(
        cls,
        item_dict: dict,
        parent: Optional["InventoryItem"] = None,
    ) -> "InventoryItem":
        """
        Builds an InventoryItem from a config dict
        If config has children (nested dicts), recursively
        build child InventoryItems and attach to parent
        """

        # get source filepath if specified
        source_path = item_dict.get("source", None)

        inventory_item = cls(
            value=item_dict["_ref"],
            type="class",
            children=[],
            parent=parent,
            source=source_path,
        )

        children = []
        for key, value in item_dict.items():
            if key == "_phones":
                for phone in value:
                    child = cls(value=phone, type="phone", parent=inventory_item)
                    children.append(child)
            elif key == "_flags":
                for flag in value:
                    child = cls(value=flag, type="flag", parent=inventory_item)
                    children.append(child)
            elif isinstance(value, dict):
                child = cls.from_config(value, parent=inventory_item)
                children.append(child)

        inventory_item.children = children
        return inventory_item

    def flatten(self) -> list["InventoryItem"]:
        """Recursively InventoryItem into a list including itself and all children."""
        items = [self]
        for child in self.children:
            items.extend(child.flatten())
        return items

    def __str__(self):
        return f"InventoryItem(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


class InventoryRegistry(Registry):
    """
    Registry for storing inventory items (phones, flags, classes).
    Instantiated directly with a pre-built `data` dict mapping inventory
    item names to `InventoryItem` objects, or a `config_objects` dict mapping
    filenames to YAML config objects.
    """

    def __init__(
        self,
        data: dict[str, InventoryItem] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        super().__init__(kind="Inventory", data=data, config_objects=config_objects)
        self._populate_subdicts()

    def _populate_subdicts(self):
        phones = {}
        flags = {}
        classes = {}
        for item in self.data.values():
            if item.type == "phone":
                phones[item.value] = item
            elif item.type == "flag":
                flags[item.value] = item
            elif item.type == "class":
                classes[item.value] = item
        self.phones = phones
        self.flags = flags
        self.classes = classes

    def load_all_configs(self) -> dict[str, InventoryItem]:
        config_items = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            # check for collisions
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate inventory item '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(
        self,
        config: dict,
    ) -> dict[str, InventoryItem]:
        top_classes = config.get("data", [])
        if not top_classes:
            logger.error("No top-level inventory classes found in config")
            return {}

        # get flat list of items
        inventory_items = []
        for item_config in top_classes.values():
            item = InventoryItem.from_config(item_config)
            flat_item = item.flatten()
            inventory_items.extend(flat_item)

        # check for item collisions
        item_values = [item.value for item in inventory_items]
        if len(item_values) != len(set(item_values)):
            duplicate_items = set([x for x in item_values if item_values.count(x) > 1])
            error = (
                f"Collision found among item values: {item_values} "
                + f"Duplicate items: {duplicate_items}"
            )
            logger.error(error)
            raise ValueError(error)

        # make dict mapping ref to item
        config_items = {item.value: item for item in inventory_items}

        return config_items

    def _get_tokens_from_class(self, item: InventoryItem) -> list[str]:
        """Recursively collect all phone/flag tokens from an InventoryItem subtree."""
        tokens = []
        if item.type in ("phone", "flag"):
            tokens.append(item.value)
        for child in item.children:
            tokens.extend(self._get_tokens_from_class(child))
        return tokens
