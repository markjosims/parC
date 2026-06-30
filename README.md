# tira_parser
Dataset and FST code for Tira morphological parsing

## Command line interface
The CLI for the Tira parser can be accessed at `src/cli.py`.
The `fire` package is used for building the CLI.
Four commands are exposed:

### Inflect word
Given a root (or gloss with the `--gloss` option) and options for each feature value, return all possible inflected forms for the given root+features.
```shell
python -m src.cli inflect_word ap --tam imperfective --deixis itive --class r
# Output:
rá ápà
```
Using `--gloss` instead of the verb root:
```shell
python -m src.cli inflect_word --gloss carry --tam imperfective --deixis itive --class r
# Output:
rá ápà
```


### Parse word
Given a string indicating a Tira word, returns all possible gloss and parses for that word.

```shell
python -m src.cli parse_word "rá ápà"
# output
rá ápà r-á áp-à carry-CLR-IT-IPFV-aux
rá ápà r-á áp-à carry-CLR-IT-IPFV-3SG.OBJ-2SG.SBJ-aux
```

### Search word
Performs fuzzy search on a query Tira word.
Returns parses in the same format as the `parse_word` command.

```shell
python -m src.cli search_word "àprìɲ"
àpɾíɲá àpɾíɲá boy-ACC-SG
ápɾíɲá àpɾíɲá boy-ACC-SG-left_h
àpɾì<ENDOFSENTENCE> àpɾí boy-NOM-SG-final_lowering
ápɾì<ENDOFSENTENCE> àpɾí boy-NOM-SG-final_lowering-left_h
àpɾí<ENDOFSENTENCE> àpɾí boy-NOM-SG
àpɾí àpɾí boy-NOM-SG
ápɾí<ENDOFSENTENCE> àpɾí boy-NOM-SG-left_h
ápɾí àpɾí boy-NOM-SG-left_h
àpɾìɲà<ENDOFSENTENCE> àpɾíɲá boy-ACC-SG-final_lowering
ápɾìɲà<ENDOFSENTENCE> àpɾíɲá boy-ACC-SG-final_lowering-left_h
```

### Root<->Gloss
Retrieve the gloss for a given root or the root for a given gloss.

```shell
python -m src.cli get_gloss_for_root ap
# output
carry

python -m src.cli get_root_for_gloss carry
# output
ap
```

### Search corpus
Prints all Tira sentences alongside their English translation that contain a given query string 
Uses the Python `re` module for search rather than FST-based search with Pynini.
Instead, to give the search function some flexibility, this command uses the `unidecode` package to convert unicode strings to ASCII characters.
This means that IPA letters will be converted to their closest ASCII equivalent and any diacritics will be removed.
Thus, the query "apri" will match strings like "àpɾí" "âprì" "ápɽɪ̀".
To search for sentences where the *translation* matches the query, use the `--query_type en` flag.

```shell
python -m src.cli search_corpus apri
# output
["ùrnɔ̀ ŋàcí áprɪ́ɲá kúkùŋ", "The grandfather gave the boy to Kuku"]
["ùrnɔ̀ kə̀ŋàcí áprɪ́ɲá kúkùŋ", "The grandfather gave the boy to Kuku"]
["ùrnɔ̀ kə̀ŋàcí kúkùŋ àprɪ̀ɲà", "The grandfather gave Kuku to the boy"]

python -m src.cli search_corpus boy --query_type en
# output
["ùrnɔ̀ ŋàcí áprɪ́ɲá kúkùŋ", "The grandfather gave the boy to Kuku"]
["ùrnɔ̀ kə̀ŋàcí áprɪ́ɲá kúkùŋ", "The grandfather gave the boy to Kuku"]
["ùrnɔ̀ kə̀ŋàcí kúkùŋ àprɪ̀ɲà", "The grandfather gave Kuku to the boy"]
```

Since it uses the `re` library regexes are supported in the query.

```shell
python -m src.cli search_corpus "v@?led"
# output
["lùrnɔ̀ lávə̀lɛ̀ðɔ̀", "The grandchildren will pull "]
["lòtùwɛ́l lávə̀lɛ̀ðɔ́ ðáŋàlà", "the monkeys will pull the sheep (towards)"]
["lɛ́vlɛ̀ðɔ́lŋù", "S/he pulled them here (puts emphasis on initial syllable)"]
["ðə̀vlɛ̀ðɔ́", "it (sheep) pulled it (dog) (towards)"]

python -m src.cli search_corpus "countr(y|ies)" --query_type en
# output
["ɲɛ́́n", "countries"]
["ɲɛ̀ɛ̀n", "countries"]
["àjɛ̀n", "country, hill, mountain"]
["àjɛ̌n", "country, hill, mountain"]
```

## Overview [DATED!]
The Tira parser can perform morphological decomposition and analysis of Tira text. A simple analyzed sentence is given below,
where 'Sentence' corresponds to a transcription without any analysis or decomposition, 'Parse' is the morphologically decomposed
version of the same transcription and 'Gloss' is the morpheme-by-morpheme translation.

    | Sentence  | kúkù         | kə̀pɔ́                      | ɛ́nà           |
    | Parse     | kúkù         | kə̀-p-ɔ́                    | ɛ́nà           |
    | Gloss     | (Clg)Kuku    | Clg-beat-FV.Vent.Pfv      | hunted.animal |

Given the 'Sentence' row as input, the parser will output the 'Parse' and 'Gloss' rows.
The parser will need to account not just for concatenative morphology but also more complex processes such as tonal exponence.

    | Sentence  | lɛ̀ré  | lɛ̂ré      |
    | Parse     | lɛ̀ré  | <H>+lɛ̀ré  |
    | Gloss     | bowl  | bowl.LOC  |

Tone processes can also be long distance.
The parser will, ideally, be able to account for the fact that the initial high tone on \[kárɔ́gɛ́] /k-àr-ɔ́-gɛ́/
comes from the sentence-initial focus particle /àn/.

    | Sentence  | àn        | ɔ́ndì  | kárɔ́gɛ́                    | lúrnɔ̀             | kə̀r̀lɛ̀ɲí               | ŋɛ́n   |
    | Parse     | àn^<H>    | ɔ́ndì  | <H>+k-àr-ɔ́-gɛ́             | l-úrnɔ̀            | kə̀-r̀lɛ̀ɲ-í             | ŋɛ́n   |
    | Gloss     | FOC       | what  | Clg-say-FV.Vent.Pfv-Wh    | CLl-grandfather   | Clg-chase-FV.Vent.Pfv | dog   |

Tira is an under-studied language, and the data to be processed come from various stages of the lifecycle of the project and do not reflect a consistent transcription convention, as is often the case when documenting a language.
For the parser to be able to process human annotations, it will need to be able to handle fuzzy matches.
For example the word /ùnɛ́ɾɛ́/ 'yesterday' can be found transcribed \[únːɛ̀ːɾɛ̀], \[ūnːɛ̄ːɾɛ̀], \[ùnɛ̀ré], and the word /t̪òlé/ 'lion' can be found transcribed \[t̪òlí], \[t̪ʊ̀lɪ́], \[t̪ùlí] etc.
Ideally, fuzzy search should be able to account for the possible variation encountered in Tira transcriptions and enforce
a consistent standard.

## Methods
The Tira parser relies on FST technology with the Pynini python package as an interface.
Rules for morphological exponence for Tira are adapted from the analysis given in Hagen Kaldhol (2024).
Pynini provides functions for efficient creation of context-dependent rewrite rules that are ideal for handling the complex patterns of exponence present in Tira.
In addition, the `pynini.lib.paradigms` module allows for easy creation and organization of morphological paradigms including transducing inflected forms to glosses and vice versa.

## Workflow

## Dependencies
### Linux
Should just need `pip install -r requirements.txt`

### MacOS
Pynini requires [OpenFST 1.8.3](https://www.openfst.org/twiki/bin/view/FST/FstDownload).
Earlier versions might work as well.
If using 1.8.3 note the patch described in [this github issue](https://github.com/gpustack/gpustack/issues/1798#issuecomment-2980869111).

Once OpenFST is installed, `pip install -r requirements.txt` should work.

### Windows
Pynini is difficult to install on Windows, I suggest using WSL and following the Linux instructions.