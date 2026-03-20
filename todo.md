# todo
## Web app
- [x] Interactive I/O testing in rule editor [!CLAUDE]
- [x] Rename `FeatureRegistry` to `FeatureValuesRegistry` [!MARK]
- [x] `FeatureRegistry` orchestrates `FeatureValuesRegistry` and `FeatureCombinationsRegistry` [!MARK]
- [x] Marker registries pass tests
- [ ] Feature editor
    - Instantiate a `FeatureRegistry`
- [ ] Feature combinations editor
    - Should check against `FeatureRegistry` that features and values are supported
- [ ] Marker editor
    - Should also validate against `FeatureRegistry`
- [ ] Implement `Paradigm` class
    - Orchestrates `FeatureRegistry`, `FstRegistry`, `MarkerRegistry`
    - Query features set -> `List[Marker]`
    - Easy I/O verification of `$stem` -> `List[Marker]` -> `$inflected_form`
- [ ] Implement `ParadigmRegistry`
- [ ] Paradigm editor