# todo
## Web app
### Pages
- [x] Interactive I/O testing in rule editor [!CLAUDE]
- [ ] Feature editor [!CLAUDE]
- [x] Replace stateful `FstRegistry` with `GrammarRegistry` [!MARK]
- [ ] Feature combinations editor [!CLAUDE]
    - Should check against `FeatureRegistry` that features and values are supported [!CLAUDE]
- [ ] Marker editor [!CLAUDE]
    - Should also validate against `FeatureRegistry` (contained in `GrammarRegistry`) [!CLAUDE]
- [ ] Paradigm editor [!CLAUDE]
### UI/UX
- [ ] Save YAML button sticks at top of page [!CLAUDE]
- [ ] Option to rename or delete YAML files [!CLAUDE]
## Parser backend
- [x] Rename `FeatureRegistry` to `FeatureValuesRegistry` [!MARK]
- [x] `FeatureRegistry` orchestrates `FeatureValuesRegistry` and `FeatureCombinationsRegistry`
- [x] Marker registries pass tests
- [ ] Implement `GrammarRegistry` [!MARK]
    - Orchestrates **all** registries for an entire language project
    - [x] Start by just encapsulating `FstRegistry`, `FeatureRegistry` and `MarkerRegistry`
    - [ ] Exposes core functionality from each registry, e.g. `FstRegistry.fsa()`, `MarkerRegistry.feature_markers`, `MarkerRegistry.contingent_markers`, `Lexicon...`
- [ ] Implement `Paradigm` class [!MARK]
    - Orchestrates `FeatureRegistry`, `FstRegistry`, `MarkerRegistry`
    - Query features set -> `List[Marker]`
    - Easy I/O verification of `$stem` -> `List[Marker]` -> `$inflected_form` using `Paradigm.inflect_stem(stem, features) -> pynini.Fst` method
    - `Paradigm.output_paradigm(stem) -> List[Dict[str, str]]` gives a list of **all inflected forms* for a given stem that the paradigm supports
        - include `require_features: Dict[str, List[str]]` and `exclude_features: Dict[str, List[str]]` args to constrain feature space (e.g. passing `require_features={"class": ['l', 'unmarked']}` will only output verb forms marked with 'l' class or with an unmarked class value)
- [ ] Implement `PartOfSpeechRegistry` with child class `Lexicon` [!MARK]
- [ ] Define logic for filtering stems belonging to a particular paradigm
## Housekeeping
- Error messages should trigger logs, and the code for this should be DRY.