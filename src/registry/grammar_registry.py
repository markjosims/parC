"""
Implements the `Paradigm` and `GrammarRegistry` classes, which
are the highest-level objects in the registry system.

The `Paradigm` class describes a paradigm or sub-paradigm in the
linguistic sense, represented here as a set of `Marker` lists over
a feature space. It also provides logic for defining the order of
application for markers, and for selecting stems and principle parts
from the lexicon.

The `GrammarRegistry` class orchestrates all registries for a given language.
[At present, the `GrammarRegistry` is essentially a wrapper over the
`MarkerRegistry` and `FstRegistry`, but it will eventually also include
the `LexiconRegistry`, and will directly load in `Paradigm` objects.
Since paradigm objects are themselves the the highest level of abstraction
in the registry system, there is no intermediate `ParadigmRegistry` class.]
"""

from loguru import logger

from src.registry.registry_utils import Registry
from src.registry.marker_registry import (
    Marker, MarkerRegistry, FeatureMarkers, ContingentMarkers
)
from src.registry.fst_registry import FstRegistry
from src.registry.feature_registry import FeatureRegistry, FeatureValueCombinations
from src.registry.lexicon_registry import LexiconRegistry, PartOfSpeech, Lexicon
from typing import Any, Dict, Dict, List, Optional

class Paradigm:
    """
    Object for combining marker objects based on multiple feature values.
    Allows combination of standard marker objects (i.e. for one feature each)
    and contingent marker objects (i.e. for multiple features simultaneously).
    Contingent marker objects are given priority when combining.

    Validates that all feature values in the feature_value_combinations are
    recognized by the provided marker objects and that no 'order' values in
    the marker objects are unrecognized.

    Allows for querying of marker combinations based on feature values,
    and also provides string I/O with marker transducers.

    The `__init__` function expects all markers and contingent markers to be
    passed directly, whereas the `from_config` factory method expects a
    `MarkerRegistry` object from which it can pull the relevant marker objects,
    and constructs any inline markers as needed.
    """

    def __init__(
        self,
        markers: List[FeatureMarkers],
        contingent_markers: List[ContingentMarkers],
        marker_order: List[str],
        part_of_speech: PartOfSpeech,
        lexicon: Lexicon,
        feature_value_combinations: Optional[FeatureValueCombinations] = None,
        fst_registry: Optional[FstRegistry] = None,
    ):
        self.feature_value_combinations = feature_value_combinations
        self.features = feature_value_combinations.features
        self.marker_order = marker_order
        self.part_of_speech = part_of_speech
        self.lexicon = lexicon
        self.markers = markers
        self.contingent_markers = contingent_markers
        self.fst_registry = fst_registry

        self.fst_registry_initialized = False
        if self.fst_registry and self.fst_registry.is_initialized:
            self.fst_registry_initialized = True
        else:
            logger.info(
                "FST registry not provided or not initialized. "
                "FST-based operations will not be available until the registry is initialized."
            )

    def from_config(
        cls,
        marker_registry: MarkerRegistry,
        lexicon_registry: LexiconRegistry,
        config: Dict[str, Any]
    ) -> 'Paradigm':
        """
        Factory method for constructing a Paradigm object from a MarkerRegistry
        and a FeatureValueCombinations object. This method will pull the relevant
        marker objects from the MarkerRegistry based on the provided features,
        and will construct any inline markers as needed.
        """

        # load part of speech and lexicon
        part_of_speech_name = config['part_of_speech']
        part_of_speech, lexicon = lexicon_registry[part_of_speech_name]
        
        # load simplex markers for each feature
        markers = []
        for feature, marker_map in config['markers'].items():
            if feature not in part_of_speech.features:
                raise ValueError(
                    f"Feature '{feature}' in paradigm config not recognized in part of speech '{part_of_speech_name}'."
                )

            # get any set-wide attributes            
            inherited_marker_set = marker_map.pop('inherits', None)
            marker_order = marker_map.pop('global_order', None)

            markers = FeatureMarkers(feature_name=feature)

            if inherited_marker_set:
                inherited_marker_set = inherited_marker_set.remove_prefix('$')
                if inherited_marker_set not in marker_registry.feature_markers:
                    raise ValueError(
                        f"Marker set '{inherited_marker_set}' specified for feature '{feature}' in paradigm config not found in marker registry."
                    )
                markers = marker_registry.feature_markers[inherited_marker_set]
            
            # read in any inline markers, which will override inherited markers
            # all other keys should be feature values mapping to marker lists
            expected_feature_values = ...
            for feature_value, marker_list in marker_map.items():
                if feature_value in markers.markers:
                    logger.info(
                        f"Feature value '{feature_value}' for feature '{feature}' in paradigm config is overriding an existing marker set. "
                        f"Existing marker set will be ignored for this feature value."
                    )
                # need to validate against expected feat vals here?
                # we really should just reuse the FeatureMarkers loading logic here,
                # no need to duplicate it
                markers.markers[feature_value] = marker_list


    #     recognized_features = marker_objects.keys()

    #     self.marker_objects = marker_objects

    #     # verify no overlap in contingent marker feature sets
    #     contingent_features = []
    #     for contingent_marker in contingent_marker_objects:
    #         for feature in contingent_marker.feature_names:
    #             if feature in contingent_features:
    #                 raise ValueError(
    #                     f"Overlapping feature '{feature}' in contingent feature maps."
    #                 )
    #         contingent_features.extend(contingent_marker.feature_names)

    #     self.contingent_marker_objects = contingent_marker_objects

    #     recognized_features = set(recognized_features).union(contingent_features)
    #     if set(self.feature_names) != recognized_features:
    #         raise ValueError(
    #             f"Feature names in feature_value_combinations do not match "
    #             f"those in marker_objects and contingent_marker_objects. "
    #             f"Expected {self.feature_names}, got {recognized_features}."
    #         )
        
    #     self.data = self._populate_data()

    # def _get_marker_dict(
    #     self,
    #     **feature_values: str
    # ) -> List[Dict[str, str]]:
    #     """
    #     Get the marker dictionary for a given feature combination.
    #     This performs non-hashed searching through all provided marker objects,
    #     and is used during init to build the hashtable for efficient querying.
    #     """
    #     provided_features = set(feature_values.keys())
    #     expected_features = set(self.feature_names)
    #     if provided_features != expected_features:
    #         raise ValueError(
    #             f"Provided feature values do not match expected features. "
    #             f"Expected {expected_features}, got {provided_features}."
    #         )

    #     features_to_match = provided_features.copy()
    #     marker = []

    #     # first check contingent markers
    #     for contingent_marker_map in self.contingent_marker_objects:
    #         features_for_marker = contingent_marker_map.feature_names
    #         feature_subset = {feature: feature_values[feature] for feature in features_for_marker}
    #         marker_part = contingent_marker_map.get_marker(**feature_subset)
    #         if marker_part:
    #             marker.extend(marker_part)
    #             features_to_match -= set(features_for_marker)
        
    #     # then check standard markers
    #     for feature in features_to_match:
    #         marker_map = self.marker_objects[feature]
    #         feature_value = feature_values[feature]
    #         marker_part = getattr(marker_map, feature_value, {})
    #         if marker_part:
    #             marker.extend(marker_part)
    #         else:
    #             raise KeyError(
    #                 f"No marker found for feature '{feature}' with value '{feature_value}'."
    #             )

    #     # ensure marker 'order' values are recognized
    #     for m in marker:
    #         order = m.get('order')
    #         if order and order not in self.marker_order:
    #             raise ValueError(
    #                 f"Marker order '{order}' not recognized. "
    #                 f"Expected one of {self.marker_order}."
    #             )

    #     # sort marker parts according to specified order
    #     marker.sort(
    #         key=lambda m: self.marker_order.index(m.get('order', float('inf')))
    #     )

    #     return marker


    # def _populate_data(self) -> Dict[str, List[Dict[str, str]]]:
    #     """
    #     Build a dictionary mapping feature combination strings to marker lists.
    #     """
    #     all_combinations = self.feature_value_combinations.get_all_combinations()
    #     data = {}
    #     for combination in all_combinations:
    #         marker_list = self._get_marker_dict(**combination)
    #         key = self._stringify_feature_dict(combination)
    #         data[key] = marker_list

    #     return data
    
    # def to_pandas(self) -> pd.DataFrame:
    #     """
    #     Convert the paradigm markers data to a pandas DataFrame.
    #     Each row corresponds to a feature combination and its associated markers.
    #     """
    #     records = []
    #     for feature_str, markers in self.data.items():
    #         feature_dict = self._feature_str_to_dict(feature_str)
    #         record = {**feature_dict, 'markers': markers}
    #         records.append(record)
    #     return pd.DataFrame(records)

    def _build_all_marker_transducers(self):
        for marker_set in self.feature_markers.values():
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)
        for marker_set in self.contingent_markers.values():
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)

    def _build_marker_transducer(self, marker: Marker):
        if marker.type == 'rule':
            marker_rule = self.fst_registry.rules[marker.value]
        elif marker.type == 'prefix':
            marker_rule = self.fst_registry.prefix(marker.value)
        elif marker.type == 'suffix':
            marker_rule = self.fst_registry.suffix(marker.value)
        elif marker.type == 'replace':
            marker_rule = self.fst_registry.replace_transducer(
                marker.value[0], marker.value[1]
            )
        elif marker.type == 'suppletion':
            sigma_star = '<Sigma>*'
            marker_rule = self.fst_registry.replace_transducer(
                sigma_star, marker.value
            )
        marker.set_transducer(marker_rule.fst)

class GrammarRegistry(Registry):
    """
    Orchestrates all registries for a given language.
    """
    def __init__(
        self,
        marker_registry: MarkerRegistry,
        lexicon_registry: LexiconRegistry,
        paradigms: Optional[List[Paradigm]] = None,
    ):
        self.marker_registry = marker_registry
        self.lexicon_registry = lexicon_registry
        
        self.fst_registry: FstRegistry = marker_registry.fst_registry
        self.feature_registry: FeatureRegistry = marker_registry.feature_registry

        self.paradigms = paradigms or []
    
    @classmethod
    def from_config_dir(cls, config_dir: str) -> 'GrammarRegistry':
        """
        [TODO: implement factory method]
        """
        return cls(
            marker_registry=MarkerRegistry.from_config_dir(config_dir),
            lexicon_registry=LexiconRegistry.from_config_dir(config_dir),
        )
    
# class FeatureQueryMixin:
#     """
#     Mixin providing methods for querying markers based on feature dictionaries.
#     Converts between 'feature=value feature=value' strings and dicts, with
#     consistent alphabetical ordering of features.
#     """

#     def _feature_str_to_dict(self, feature_str: str) -> Dict[str, str]:
#         """Convert 'feature=value feature=value' string to a dict."""
#         feature_dict = {}
#         for feature_value in feature_str.split(' '):
#             feature, value = feature_value.split('=')
#             feature_dict[feature] = value
#         return feature_dict

#     def _stringify_feature_dict(self, feature_dict: Dict[str, str]) -> str:
#         """Convert a feature dict to a sorted 'feature=value feature=value' string."""
#         return ' '.join(
#             f"{feature}={value}"
#             for feature, value in sorted(feature_dict.items())
#         )

#     def get_marker(self, **feature_dict: str) -> MarkerList:
#         """Retrieve markers for a given set of feature values."""
#         key = self._stringify_feature_dict(feature_dict)
#         data = getattr(self, 'data', None)
#         if data is None:
#             raise ValueError("No data attribute found.")
#         if key not in data:
#             raise KeyError(f"No marker found for feature combination: {key}")
#         return data[key]