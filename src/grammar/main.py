from tqdm import tqdm

from src.grammar.acceptor_compilation import build_fst_context_for_project
from src.grammar.marker_resolution import (
    build_all_paradigm_global_markers,
    build_all_paradigm_tries,
)
from src.grammar.paradigm_compilation import compile_global_parser
from src.grammar.transducer_compilation import compile_rules_for_project
from src.yaml.yaml_server import load_project_structs


def compile_project():
    num_steps = 6
    pbar = tqdm(total=num_steps, desc="Compiling project")
    project = load_project_structs()
    pbar.update(1)
    project = build_fst_context_for_project(project)
    pbar.update(1)
    project = compile_rules_for_project(project)
    pbar.update(1)
    project = build_all_paradigm_tries(project)
    pbar.update(1)
    project = build_all_paradigm_global_markers(project)
    pbar.update(1)
    parser = compile_global_parser(project)
    pbar.update(1)

    return project, parser


if __name__ == "__main__":
    project, parser = compile_project()
