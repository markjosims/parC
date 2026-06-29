"""
FastAPI backend for parC grammar.
Provides following endpoints:
- `GET /schema/<kind>`: Retrieve the schema for a specific configuration kind.
- `GET /configs/<kind>`: List all configuration files for a specific kind.
- `GET /file/<kind>/<path>`: Read a specific configuration file.
- `PUT /file/<kind>/<path>`: Update a specific configuration file.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.yaml_utils.yaml_server import (
    get_yaml_kind,
    get_inventory_items,
    get_feature_map,
    get_patterns,
    get_rules,
    get_inflection_stages,
    get_yaml_data_safe,
)

app = FastAPI()


@app.get("/grammar-stats")
def grammar_stats() -> dict:

    grammar_stats = {}

    inventory_stats = {}
    inventory_items = get_inventory_items()
    inventory_yaml = get_yaml_kind("Inventory")
    inventory_stats["files"] = len(inventory_yaml["valid"])
    inventory_stats["invalid_files"] = len(inventory_yaml["invalid"])
    inventory_stats["phones"] = len(inventory_items.phones)
    inventory_stats["tags"] = len(inventory_items.tags)
    inventory_stats["classes"] = len(inventory_items.item_map)
    grammar_stats["inventory"] = inventory_stats

    feature_definitions_stats = {}
    feature_definitions_yaml = get_yaml_kind("FeatureDefinitions")
    features = get_feature_map()
    feature_definitions_stats["files"] = len(feature_definitions_yaml["valid"])
    feature_definitions_stats["invalid_files"] = len(
        feature_definitions_yaml["invalid"]
    )
    feature_definitions_stats["total"] = len(features)
    grammar_stats["feature_definitions"] = feature_definitions_stats

    feature_markers_stats = {}
    feature_markers_yaml = get_yaml_kind("FeatureMarkers")
    feature_markers_stats["files"] = len(feature_markers_yaml["valid"])
    feature_markers_stats["invalid_files"] = len(feature_markers_yaml["invalid"])
    feature_markers_stats["total"] = sum(
        len(file["markers"]) for _, file in feature_markers_yaml["valid"]
    )
    feature_markers_stats["inflection_stages"] = len(get_inflection_stages())
    grammar_stats["feature_markers"] = feature_markers_stats

    contingent_markers_stats = {}
    contingent_markers_yaml = get_yaml_kind("ContingentFeatureMarkers")
    contingent_markers_stats["files"] = len(contingent_markers_yaml["valid"])
    contingent_markers_stats["invalid_files"] = len(contingent_markers_yaml["invalid"])
    contingent_markers_stats["total"] = sum(
        len(file["markers"]) for _, file in contingent_markers_yaml["valid"]
    )
    grammar_stats["contingent_markers"] = contingent_markers_stats

    patterns_stats = {}
    patterns_yaml = get_yaml_kind("Patterns")
    patterns = get_patterns()
    patterns_stats["files"] = len(patterns_yaml["valid"])
    patterns_stats["invalid_files"] = len(patterns_yaml["invalid"])
    patterns_stats["total"] = len(patterns)
    grammar_stats["patterns"] = patterns_stats

    rules_stats = {}
    rules_yaml = get_yaml_kind("Rules")
    rules = get_rules()
    rules_stats["files"] = len(rules_yaml["valid"])
    rules_stats["invalid_files"] = len(rules_yaml["invalid"])
    rules_stats["total"] = len(rules)
    grammar_stats["rules"] = rules_stats

    paradigm_stats = {}
    paradigm_yaml = get_yaml_kind("Paradigm")
    paradigm_stats["files"] = len(paradigm_yaml["valid"])
    paradigm_stats["invalid_files"] = len(paradigm_yaml["invalid"])
    grammar_stats["paradigms"] = paradigm_stats

    part_of_speech_stats = {}
    part_of_speech_yaml = get_yaml_kind("PartOfSpeech")
    part_of_speech_stats["files"] = len(part_of_speech_yaml["valid"])
    part_of_speech_stats["invalid_files"] = len(part_of_speech_yaml["invalid"])
    grammar_stats["part_of_speech"] = part_of_speech_stats

    return grammar_stats


@app.get("/health")
def health_check():
    return {"status": "healthy"}


class InflectRequest(BaseModel):
    kind: str = "paradigm"
    name: str
    stems: list[str]
    features: dict[str, str]


class ParseRequest(BaseModel):
    kind: str = "paradigm"
    name: str
    form: str


@app.get("/inflection-meta")
def inflection_meta():
    feature_map = get_feature_map()

    paradigms = []
    paradigm_yaml = get_yaml_kind("Paradigm")
    for basename, data in paradigm_yaml["valid"]:
        part_of_speech = get_yaml_data_safe(
            yaml_basename=data["part_of_speech"], kind="PartOfSpeech"
        )
        paradigms.append(
            {
                "name": os.path.splitext(basename)[0],
                "features": part_of_speech["features"],
                "lexical_features": part_of_speech["lexical_features"],
            }
        )

    return {
        "features": feature_map,
        "paradigms": paradigms,
    }


@app.get("/roots")
def get_roots(kind: str, name: str):
    """
    Get the roots of a paradigm or lexicon.
    """
    # TODO


@app.get("/lexical-features")
def get_lexical_features(kind: str, name: str, root: str):
    """
    Get the lexical features of a single root in a paradigm or lexicon.
    """
    # TODO


@app.get("/patterns")
def get_patterns_route():
    return get_patterns()


@app.get("/rules")
def get_rules_route():
    return get_rules()


class TestPatternRequest(BaseModel):
    pattern: str
    test_includes: list[str] = []
    test_excludes: list[str] = []


@app.post("/test-pattern")
def api_test_pattern(req: TestPatternRequest):
    try:
        # TODO: implement acceptor_compilation.py
        result = None
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


class TestRuleRequest(BaseModel):
    rule: str
    test_mappings: list[list[str]]


@app.post("/test-rule")
def api_test_rule(req: TestRuleRequest):
    # TODO: implement transducer_compilation.py
    try:
        result = None
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/inflect")
def api_inflect(req: InflectRequest):
    try:
        forms = []
        stages = []
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"forms": forms, "stages": stages}


@app.post("/parse")
def api_parse(req: ParseRequest):
    try:
        parses = []
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"parses": parses}


app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
