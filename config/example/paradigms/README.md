# paradigms
Configs defining inflectional paradigms.
The name 'paradigm' here is agnostic to *exhaustive* or *sub-*paradigms.
For example, a `Paradigm` config may correspond to all possible inflected verb forms for an entire language (not recommended), or a sub-paradigm for a specific TAM value for a particular conjugation class (recommended).
An inflectional paradigm must have at minimum the attributes 'part_of_speech' and 'features'.
```yaml
kind: Paradigm
part_of_speech: verb
features:
  person: $person_suffixes
  tense: present
  mood: $mood_stem_vowel
```
The 'features' attribute may contain the name of a `FeatureMarkers` config corresponding to that feature or string indicating a single feature value.
Here we import 'features/person_suffixes.yaml' and 'features/mood_stem_vowel.yaml' to mark the person and mood features respectively.
If the latter, only that feature will be used for the paradigm, and the feature will be zero-marked.
Marker objects can also be specified within the `Paradigm` config, i.e.
```yaml
kind: Paradigm
part_of_speech: verb
features:
  person: $person_suffixes
  tense: present
  mood:
    indicative: null
    subjunctive:
      rule: $subjunctive_stem_vowel
```
Here, rather than loading in a `FeatureMarkers` config for mood, we define a markers config where the indicative mood is zero-marked and the subjunctive mood is marked with a stem vowel change defined by a rule loaded in from the `config/rules/` directory.

The 'contingent_features' attribute may be specified alongside 'features', which imports a `ContingentFeatures` config or list of configs.
```yaml
kind: Paradigm
part_of_speech: verb
features:
  person: $person_suffixes
  tense:
    present: null
    past: $past_tense_stem
  mood: $mood_stem_vowel
contingent_features:
  - $past_tense_person_markers
```
`ContingentFeatures` definitions can also be declared in-line, or imported configs can be composed.
```yaml
kind: Paradigm
part_of_speech: verb
features:
  person: $person_suffixes
  tense:
    present: null
    past: $past_tense_stem
  mood: $mood_stem_vowel
contingent_features:
  tense:
    past:
      mood:
        indicative:
          inherits: $past_tense_indicative_person_markers
        subjunctive:
          inherits: $past_tense_subjunctive_person_markers
```
The 'feature_combinations' attribute may be used to specify what combinations of features are possible for the given paradigm by importing a `FeatureCombinations` config.
```yaml
kind: Paradigm
part_of_speech: verb
features:
  mood: imperative
  person: $imperative_suffixes
feature_combinations: $imperative_person_values
```
The 'order' attribute allows specifying the order of application of markers, e.g.:
```yaml
kind: Paradigm
part_of_speech: verb
order: [person_suffix, stress_assignment, diphthongization]
features:
  person: $person_suffixes
  tense:
    present: null
    past: $past_tense_stem
  mood: $mood_stem_vowel
contingent_features:
  - $past_tense_person_markers
```
Where the various `FeatureMarkers` and `ContingentFeatureMarkers` configs must reference the stages enumerated in the 'order' attribute.
Any rules that lack an 'order' attribute will be applied last, following all ordered markers.
While ordering is optional, we strongly recommend treating it as obligatory to prevent unexpected interactions between different morphological formatives.

The 'filter' attribute allows the paradigm to select certain lexical roots and not others.
For example, we could create a paradigm that selects only Spanish verbs that exhibit an alternation between *n* and *ng* (e.g. tener/tengo/tienes).
Assuming this is indicated in the [lexicon](data/lexicon/README.md) with a lexical flag "`<n_ng_alternation>`", we can do this by selecting only verbs with this flag.
```yaml
kind: Paradigm
part_of_speech: verb
filter:
  lexical_flag: "<n_ng_alternation>"
features:
  person: $person_suffixes_with_stem_change
contingent_features:
  - $past_tense_person_markers
```
Principal parts... [TODO]