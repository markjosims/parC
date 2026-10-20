"""
Command-line entrypoint and REPL for inflecting lexemes.

Every CLI argument is optional: anything left out is prompted for. After
each inflection the REPL accepts `key=value` edits to the paradigm, root,
homophone index or any inflectional feature, overriding CLI values, so the
project is only compiled once per session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import Validator
from tabulate import tabulate

if TYPE_CHECKING:
    from src.models import InflectedWord, Project

app = typer.Typer(add_completion=False)

PARADIGM_KEY = "paradigm"
ROOT_KEY = "root"
HOMOPHONE_INDEX_KEY = "homophone_index"

REPL_HINT = (
    "Edit with KEY=VALUE (paradigm, root, homophone_index or a feature); "
    "KEY= unsets it. Empty line picks new features, Ctrl-D quits."
)


@dataclass
class ReplState:
    paradigm_id: str | None = None
    root: str | None = None
    homophone_index: int = 0
    features: dict[str, str] = field(default_factory=dict)

    def __str__(self):
        features = "".join(f"[{key}={value}]" for key, value in sorted(self.features.items()))
        return f"{self.paradigm_id} · {self.root} · #{self.homophone_index} · {features}"


def _parse_assignments(tokens: list[str]) -> dict[str, str]:
    assignments = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep or not key:
            raise ValueError(f"Expected KEY=VALUE, got {token!r}")
        assignments[key.strip()] = value.strip()
    return assignments


def _error(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)


def _paradigm_feature_space(project: Project, paradigm_id: str) -> list[dict[str, str]]:
    from src.grammar.marker_resolution import get_trie_feature_space

    feature_space = get_trie_feature_space(project.inflect_tries[paradigm_id])
    return [feature_set.to_dict() for feature_set in feature_space]


def _feature_ids(feature_space: list[dict[str, str]]) -> set[str]:
    return {feature for feature_dict in feature_space for feature in feature_dict}


def _apply_assignments(
    state: ReplState,
    assignments: dict[str, str],
    project: Project,
) -> None:
    """
    Update `state` in place. Invalid assignments are reported and skipped.
    The paradigm is applied first so features are checked against it, and
    features the new paradigm lacks are dropped.
    """
    paradigms = project.struct_registry["ParadigmFile"]
    if PARADIGM_KEY in assignments:
        paradigm_id = assignments.pop(PARADIGM_KEY) or None
        if paradigm_id is not None and paradigm_id not in paradigms:
            _error(f"No paradigm {paradigm_id!r}; expected one of: {', '.join(paradigms)}")
        else:
            state.paradigm_id = paradigm_id
    feature_ids = (
        _feature_ids(_paradigm_feature_space(project, state.paradigm_id))
        if state.paradigm_id
        else None
    )
    if feature_ids is not None:
        state.features = {
            key: value for key, value in state.features.items() if key in feature_ids
        }

    for key, value in assignments.items():
        if key == ROOT_KEY:
            state.root = value or None
        elif key == HOMOPHONE_INDEX_KEY:
            try:
                state.homophone_index = int(value or 0)
            except ValueError:
                _error(f"{HOMOPHONE_INDEX_KEY} must be an integer, got {value!r}")
        elif feature_ids is not None and key not in feature_ids:
            _error(f"Paradigm {state.paradigm_id!r} has no feature {key!r}")
        elif value:
            state.features[key] = value
        else:
            state.features.pop(key, None)


def _prompt_choice(session: PromptSession, label: str, values: list[str]) -> str:
    validator = Validator.from_callable(
        lambda text: text in values,
        error_message=f"Expected one of: {', '.join(values)}",
        move_cursor_to_end=True,
    )
    return session.prompt(
        f"{label} [{'/'.join(values)}]: ",
        completer=WordCompleter(values),
        validator=validator,
        complete_while_typing=True,
    )


def _fill_features(
    feature_space: list[dict[str, str]],
    features: dict[str, str],
    session: PromptSession,
) -> dict[str, str]:
    """
    Choose a value for each feature in order, keeping the value in `features`
    when it is licit alongside those already chosen and prompting otherwise,
    so only combinations in the paradigm's feature space are offered.
    """
    chosen = {}
    for feature in sorted(_feature_ids(feature_space)):
        consistent = [
            feature_dict
            for feature_dict in feature_space
            if all(feature_dict.get(key) == value for key, value in chosen.items())
        ]
        values = sorted(
            {feature_dict[feature] for feature_dict in consistent if feature in feature_dict}
        )
        if not values:
            continue
        if features.get(feature) in values:
            value = features[feature]
        elif len(values) == 1:
            value = values[0]
            typer.echo(f"{feature}: {value}")
        else:
            if feature in features:
                _error(f"{feature}={features[feature]} is not licit with {chosen}")
            value = _prompt_choice(session, feature, values)
        chosen[feature] = value
    return chosen


def _edit_completer(project: Project, state: ReplState) -> WordCompleter:
    words = [f"{PARADIGM_KEY}={paradigm_id}" for paradigm_id in project.struct_registry["ParadigmFile"]]
    words += [f"{ROOT_KEY}=", f"{HOMOPHONE_INDEX_KEY}="]
    if state.paradigm_id:
        words += sorted(
            {
                f"{key}={value}"
                for feature_dict in _paradigm_feature_space(project, state.paradigm_id)
                for key, value in feature_dict.items()
            }
        )
    return WordCompleter(words, WORD=True)


def _format_intermediate_table(inflected_word: InflectedWord) -> str:
    rows = []
    for step, intermediate in enumerate(inflected_word.intermediate or (), start=1):
        compiled_marker = intermediate.compiled_marker
        rows.append(
            (
                step,
                type(compiled_marker.marker).__struct_config__.tag,
                f"{compiled_marker.sourcefile_kind}:{compiled_marker.sourcefile_id}",
                str(compiled_marker.feature_set),
                "\n".join(intermediate.forms),
            )
        )
    return tabulate(
        rows,
        headers=("step", "marker", "source", "features", "forms"),
        tablefmt="simple_grid",
    )


def _print_inflected_word(inflected_word: InflectedWord) -> None:
    typer.echo(f"\n{inflected_word.tagged_root}")
    if inflected_word.lexeme.gloss:
        typer.echo(f"gloss: {inflected_word.lexeme.gloss}")
    typer.echo(_format_intermediate_table(inflected_word))
    typer.secho(
        f"forms: {', '.join(inflected_word.forms or ())}\n",
        bold=True,
    )


@app.command()
def inflect(
    paradigm_id: Annotated[
        Optional[str], typer.Argument(help="Id of the Paradigm config.")
    ] = None,
    root: Annotated[
        Optional[str], typer.Argument(help="Root form as listed in the lexicon.")
    ] = None,
    feature: Annotated[
        Optional[list[str]],
        typer.Option(
            "--feature",
            "-f",
            help="Inflectional feature value as FEATURE=VALUE. Repeatable.",
        ),
    ] = None,
    homophone_index: Annotated[
        int,
        typer.Option(
            "--homophone-index",
            "-i",
            help="Which of several homophonous roots to inflect.",
        ),
    ] = 0,
) -> None:
    """
    Inflect ROOT in PARADIGM_ID and show the form after each marker applies.
    Anything not given is prompted for; all values can be edited in the REPL.
    """
    try:
        feature_assignments = _parse_assignments(feature or [])
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--feature") from e

    # grammar imports are slow, keep them out of `--help`
    from src.grammar.main import compile_project
    from src.grammar.marker_resolution import get_roots_for_paradigm, inflect_lexeme
    from src.models import FeatureSet

    project, _ = compile_project()

    state = ReplState()
    _apply_assignments(
        state,
        {
            PARADIGM_KEY: paradigm_id or "",
            ROOT_KEY: root or "",
            HOMOPHONE_INDEX_KEY: str(homophone_index),
            **feature_assignments,
        },
        project,
    )

    # PromptSession keeps per-call settings like `validator` (passing None does not
    # reset them), so validated and free-text prompts need separate sessions
    choice_session = PromptSession()
    root_session = PromptSession()
    edit_session = PromptSession()
    typer.echo(REPL_HINT)
    while True:
        try:
            if state.paradigm_id is None:
                state.paradigm_id = _prompt_choice(
                    choice_session, PARADIGM_KEY, list(project.struct_registry["ParadigmFile"])
                )
            if state.root is None:
                roots = get_roots_for_paradigm(state.paradigm_id, project).root.tolist()
                state.root = root_session.prompt(
                    f"{ROOT_KEY}: ",
                    completer=WordCompleter(roots),
                )
            state.features = _fill_features(
                _paradigm_feature_space(project, state.paradigm_id),
                state.features,
                choice_session,
            )
            inflected_word = inflect_lexeme(
                paradigm_id=state.paradigm_id,
                root=state.root,
                project=project,
                inflectional_features=FeatureSet(**state.features),
                homophone_index=state.homophone_index,
            )
            _print_inflected_word(inflected_word)
        except KeyboardInterrupt:
            pass
        except EOFError:
            break
        except Exception as e:
            _error(f"{type(e).__name__}: {e}")

        try:
            line = edit_session.prompt(
                f"{state}\nparC> ",
                completer=_edit_completer(project, state),
            )
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        if not line.strip():
            state.features = {}
            continue
        try:
            _apply_assignments(state, _parse_assignments(line.split()), project)
        except ValueError as e:
            _error(str(e))


if __name__ == "__main__":
    app()
