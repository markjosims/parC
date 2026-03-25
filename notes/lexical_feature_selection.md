# lexical feature selection
Desideratum: User can reference lexical features specified within a paradigm in morphological formatives.
E.g. for Tira we might specify `[fv_class=aᴐ]` then have a rule for imperfective itive that suffixes *-à* to roots bearing this feature tag.
Or we might specify a noun as `[sg_class=ð][pl_class=j]`, then we have a rule for singular that prefixes *ð-* and plural *j-* depending on the tag.


## FST operation
I'm not aware of any way to 'edit' a rule's context after it's been compiled to a WFST.
Best might be to prepend `f"{feature_str}[BOW]<Sigma>*` to the left context then re-compile.
We need to account for the following cases:
- Simple/string map rule: Create a new rule, recycling the Tau and prepending the new condition to `left_context`
- Sequence of rules: do the above for each rule in the sequence
- Prefix/suffix: Same as first case


## Backend
Support conditioning morphological operations on the presence of lexical features
- `Paradigm` class prepends `[feature=value]` to each root for each lexically specified feature
    - Function `Paradigm.get_lexical_feature_transducer()` returns FST mapping e.g. vəlɛð -> vəlɛð[aᴐ]
    - Should apply before any other processes [TODO] continue from here!
    - Order of application: `input_str -> (principal part transducer ->) lexical feature insertion -> other marker rules` 
- `Rule` class supports an attr `Rule.lexical_features: Dict[str,str]`.
    - If present, `Rule.set_transducer` will wrap the resulting FST in a `cdrewrite` with `l=f"{feature_string}[BOW]<Sigma>*`
    - Use `fst_utils.stringify_feature_dict` to ensure consistent `Dict<-->str` mapping
    - `Marker` class also supports `lexical_features` attr, same behavior
    - Extract to function `apply_condition` in `fst_utils`? NOPE handled in vvvv FST registry vvvv
    - Inject logic to `FstRegistry._parse_rule`
        - FstRegistry first checks if feature symbols are present in inventory, if not throws error that GrammarRegistry needs to add feature symbols
        - Add validation step to paradigm registry: every rule/marker with a lexical feature should correspond to a lexical feature marked by the Lexicon class

## Frontend
User prompted to input features in format [feature=value, feature=value, feature=value]
- Note: slightly different than canonical feature string format, but more readable for users
- Serialization is easy: replace ', ' -> '][' then use `serialize_fst_string`
- Populate defaults from feature registry
