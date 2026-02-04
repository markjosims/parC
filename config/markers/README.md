# markers
YAML files for defining morphological formatives for a given feature or feature combination.
Use `FeatureMarkers` to define formatives for a single feature, and `ContingentFeatureMarkers` for formatives that apply to multiple features at once.

## FeatureMarkers
This file gives a paradigm of formatives for a single feature.
The 'feature' attribute indicates the name of the feature marked, and the 'markers' attribute is a list of dictionaries describing the formative for each value of the feature.
See [Marker keys](#marker-keys) for more details.
```yaml
# person_markers_a_stem.yaml
kind: FeatureMarkers
feature: person
markers:
  1sg:
    suffix: -o
  2sg:
    suffix: -as
  3sg:
    suffix: -a
```

## ContingentFeatureMarkers
This file gives a paradigm of formatives for multiple features at once.
This is helpful for cases where the morphological realization of one feature depends on the value of another feature.
The 'features' attribute is a list of all relevant features, and the 'markers' attribute is a nested list of dictionaries...
```yaml
# person_tense_markers_a_stem.yaml
kind: ContingentFeatureMarkers
features: [person, tense]
markers:
    tense:
        present:
            1sg:
                suffix: -o
            2sg:
                suffix: -as
            3sg:
                suffix: -a
        past:
            1sg:
                suffix: -é
            2sg:
                suffix: -aste
            3sg:
                suffix: -ó
```
Rather than list the formatives for all feature combinations, sub-paradigms can be imported from separate files using the `inherits` key:
```yaml
kind: ContingentFeatureMarkers
features: [person, tense]
markers:
    tense:
        present:
            inherits: $present_tense_markers
        past:
            inherits: $past_tense_markers
```
This allows for efficient organization and orchestration of paradigms with several interacting features.

## Marker keys
The marker dictionary corresponds to the `Marker` class in `src/forms/form_constructors.py`.
This object describes the logic for building an FST describing a morphological formative.
In the Spanish examples above, the only formative type used is 'suffix,' but several types of string operations are allowed, including:
- Suffix: Append suffix string to stem
- Prefix: Prepend prefix string to stem
- Replace: List of ["intab", "outtab"]. Replace "intab" with "outtab" across all contexts.
- Rule: Name of rule to be applied to stem. Must be defined in a `Rules` YAML file.
- Suppletion: Replace the entire stem with the given string. Note suppletion is not **not** compatible with any of the above operations, and attempting to combine them will throw an error when compiling the marker.

Alternatively, a feature attribute may simply contain `null`, indicating that the feature is zero-marked.

See below for examples of all rule types with a toy language:
```yaml
# toy_person_markers.yaml
kind: FeatureMarkers
feature: person
markers:
  # e.g. ket > pe-ket-ap
  1sg:
    suffix: -ap
    prefix: ke-
  # e.g. ket > gat
  2sg:
    replace: [e, a]
    rule: $initial_voicing
  # no change, e.g. ket > ket
  3sg: null
  # e.g. ket > pok
  1pl:
    suppletion: pok
  # e.g. ket > re-keet
  2pl:
    rule: $vowel_lengthening
    prefix: re-
  # e.g. ket > kets
  3pl:
    rule: $affrication
    
```
Feature values may contain a list of dictionaries rather than a single dictionary.
For example, imagine we apply a suffix *-te* alongside a simple assimilation rule that changes /dt/ > [tt].
```yaml
kind: FeatureMarkers
feature: person
markers:
  # e.g. ked > ked-ap
  1sg:
    suffix: -ap
  2sg:
  # e.g. ked > ket-te
  - suffix: -te
  - replace: [dt, tt]
```
Since we can specify both the 'suffix' and 'replace' attributes in a single marker dictionary, why would this be necessary?
Notice that these markers interact, the *-te* suffix feeds the assimilation /dt/.
If assimilation applies before suffixation, we'd get a malformed output \*ked-te.
We need to make sure suffixation precedes assimilation.

To do this, we can use the 'order' key which determines the formative's order of application relative to other processes.
The value of 'order' is not a numeric, it is instead a string which names a unique stage during which the process is applied.
For example, we can define 'suffixation' and 'stem_assimilation' as the names of the two stages.
```yaml
kind: FeatureMarkers
feature: person
markers:
  # e.g. ked > ked-ap
  1sg:
    suffix: -ap
  2sg:
  # e.g. ked > ket-te
  - suffix: -te
    order: suffixation
  - replace: [dt, tt]
    order: stem_assimilation
```
Since stages are identified by their name rather than a numeric value, a stage order needs to be specified which determines the sequence of processes.
This is done in the `Paradigm` config, see the [documentation](config/paradigms/README.md) for more details.

## Composition and inheritance
Other YAML configs can be imported into the current file.
In [ContingentFeatureMarkers](#contingentfeaturemarkers) we demonstrate an example of this by importing a `FeatureMarkers` subparadigm into a `ContingentFeatureMarkers` config.
This can also be done at the head of the file with the 'inherits' attribute, e.g.:
```yaml
# person_markers_oy_1sg_present.yaml
kind: FeatureMarkers
inherits: $person_markers_a_stem_present
features: person
markers:
  1sg:
    suffix: -oy
```
This allows easy creation of irregular or sub-regular paradigms where only a few forms differ from some other paradigm specified in the 'inherits' attribute.
The example above could be applied to the Spanish verbs *dar* and *estar*, which take regular a-stem suffixes in the present tense except for the 1sg form which instead takes the suffix *-oy* (ignoring for now the accent on *está*, *estás* and *están*).

We can also use inheritance with `ContingentFeatureMarkers` config files, which e.g. allows us to create a paradigm for the present and past tense forms of *estar*.
```yaml
# person_tense_markers_oy_1sg.yaml
kind: FeatureMarkers
inherits: $person_tense_markers_a_stem_present
features: person
markers:
  tense:
    present:
      1sg:
        suffix: -oy
    past:
      1sg:
        suffix: -uv-e
      2sg:
        suffix: -uv-iste
      3sg:
        suffix: -uv-o  
```
For a verb like *dar*, which takes a-stem suffixes in the present (excepting 1sg *-oy*) and e/i-stem suffixes in the past, we can use inheritance and overriding multiple times in the same file.
```yaml
# person_tense_markers_dar.yaml
kind: FeatureMarkers
feature: person
markers:
  tense:
    present:
      inherits: $person_markers_a_stem_present
      1sg:
        suffix: -oy
    past:
      inherits: $person_markers_ei_stem_past
      1sg:
        suffix: -i
```

## Global attributes and markers
A `FeatureMarkers` or `ContingentFeatureMarkers` config may also specify 'global_attributes', which sets a given attribute for all markers defined in the file.
For example, imagine that all tense markers apply at the 'inner suffixation' stage and all person markers at the 'outer suffixation' stage.
Rather than write the 'order' attribute for each marker, we can specify it under 'global_attributes'.
```yaml
kind: FeatureMarkers
feature: tense
global_attributes:
  order: inner suffixation
markers:
  present: null
  past:
    suffix: -et
  future:
    suffix: -ol
```

```yaml
kind: FeatureMarkers
feature: person
global_attributes:
  order: outer suffixation
markers:
  1sg:
    rule: $palatalization
  2sg:
    suffix: -ek
  3sg:
    suffix: -ut
```
If an individual marker specifies the same attribute as a global attribute, the individual marker's specification for that attribute will win.
```yaml
kind: FeatureMarkers
feature: person
global_attributes:
  order: outer suffixation
markers:
  1sg:
    rule: $palatalization
    order: stem_mutation
  2sg:
    suffix: -ek
  3sg:
    suffix: -ut
```
Rather than assgining a single attribute for all markers in the config, we may wish to apply an entire marker to all forms, and then let each feature value add it's own marker if needed.
For example, let's create a paradigm for the Spanish verb *estar* where we insert a suffix *-uv* to the past tense stem before the person marker:
```yaml
kind: FeatureMarkers
feature: person
markers:
  global_marker:
    suffix: -uv
    order: "Inner suffix"
  1sg:
    suffix: "-e"
    order: "Outer suffix"
  2sg:
    suffix: "-iste"
    order: "Outer suffix"
  3sg:
    suffix: "-o"
    order: "Outer suffix"
```
Of course, the added effort of specifying the suffix order here outweighs the effort of simply writing out "-uv-e", "-uv-iste", "-uv-o".