import time

from neXSim import DatasetManager
from neXSim.models import Atom, NeXSimResponse, Variable
from neXSim.utils import (pred_identifier_to_clingo_relation as to_clingo)

HYPERNYM_TRANSITIVE_CLOSURE = """
instance_of(X,Z) :- instance_of(X,Y), subclass_of(Y,Z).
subclass_of(X,Z) :- subclass_of(X,Y), subclass_of(Y,Z).
is_a(X,Y) :- instance_of(X,Y).
is_a(X,Y) :- subclass_of(X,Y).
"""

MERONYM_TRANSITIVE_CLOSURE = """
part_of(X,Z) :- part_of(X,Y), part_of(Y,Z).
"""

LCA_PROGRAM = """
entity(X) :- {r}(X,_).
entity(X) :- {r}(_,X).
notAncestor(E) :- seed(S), entity(E), not {r}(S,E).
common(E) :- entity(E), not notAncestor(E).
equiv(X,Y) :- {r}(X,Y), {r}(Y,X).
noLeastCommon(E) :- common(E), {r}(C,E), common(C), not equiv(C,E).
leastCommon(X) :- common(X), not noLeastCommon(X).
"""

import clingo

ENDLINE: str = '.\n'


def inject_facts(entities: list[str], relations: list[Atom]) -> str:
    facts = ""
    for entity in entities:
        facts += f'seed("{entity}").\n'
    for relation in relations:
        tmp = to_clingo(relation.predicate)
        facts += f'{tmp}("{relation.source_id}","{relation.target_id}").\n'

    return facts


def execute_clingo_lca(program: str, unit: list[str], out_name: str) -> list[Atom]:
    return_value: list[Atom] = []
    ctl = clingo.Control()
    my_model = None
    ctl.add("base", [], program)
    ctl.ground([("base", [])])

    with ctl.solve(yield_=True) as hnd:
        for m in hnd:
            my_model = m.symbols(atoms=True)

    for atom in my_model:
        if atom.name.startswith('leastCommon'):
            return_value.append(Atom(source_id=Variable(is_free=True, origin=unit),
                                     target_id=str(atom.arguments[0]).replace('"', ''),
                                     predicate=out_name
                                     ))
    return return_value


def parse_neo4j_result(neo4j_result) -> list[Atom]:
    parsed: list[Atom] = []

    for raw_atom in neo4j_result:
        temp_atom: Atom = Atom(source_id=raw_atom['source'],
                               target_id=raw_atom['target'],
                               predicate=raw_atom['relation'])
        parsed.append(temp_atom)

    return parsed


def compute_direct_instances(unit: list[str]) -> (list[Atom], float):
    dataset_manager = DatasetManager()
    _start = time.perf_counter()
    direct_instances = parse_neo4j_result(dataset_manager.get_direct_instances(_entities=unit))
    return direct_instances, round(time.perf_counter() - _start, 5)


def compute_direct_part_of(unit: list[str]) -> (list[Atom], float):
    dataset_manager = DatasetManager()
    _start = time.perf_counter()
    direct_part_of = parse_neo4j_result(dataset_manager.get_direct_part_of(_entities=unit))
    return direct_part_of, round(time.perf_counter() - _start, 5)


def compute_raw_subgraph_hypernyms_no_dummy_sg(unit: list[str], instances: list[Atom]) -> (list[Atom], float):
    dataset_manager = DatasetManager()
    _start = time.perf_counter()
    raw_hypernyms = parse_neo4j_result(dataset_manager.get_raw_subclass_3(_entities=unit,
                                                                          _direct_instances=instances))
    raw_hypernyms.extend(instances)
    return raw_hypernyms, round(time.perf_counter() - _start, 5)



def compute_hypernym_lca(unit: list[str], raw_hypernyms: list[Atom], upper:bool) -> (list[Atom], float):
    _start = time.perf_counter()
    hypernym_lca: list[Atom] = execute_clingo_lca(inject_facts(unit, raw_hypernyms)
                                                  + LCA_PROGRAM.format(r="is_a") + HYPERNYM_TRANSITIVE_CLOSURE,
                                                  unit, 'is_a' if not upper else 'IS_A')
    return hypernym_lca, round(time.perf_counter() - _start, 5)


def compute_raw_subgraph_meronyms_no_dummy_sg(unit: list[str], direct_part_of: list[Atom]) -> (list[Atom], float):
    dataset_manager = DatasetManager()
    _start = time.perf_counter()
    raw_meronyms = []
    if len(direct_part_of) > 0:
        raw_meronyms = parse_neo4j_result(dataset_manager.get_raw_part_of_3(_entities=unit,
                                                                             _direct_instances=direct_part_of))

    return raw_meronyms, round(time.perf_counter() - _start, 5)



def compute_meronym_lca(unit: list[str], raw_meronyms: list[Atom], upper:bool) -> (list[Atom], float):
    _start = time.perf_counter()
    meronym_lca: list[Atom] = execute_clingo_lca(inject_facts(unit, raw_meronyms)
                                                 + LCA_PROGRAM.format(r="part_of") + MERONYM_TRANSITIVE_CLOSURE,
                                                 unit, 'part_of' if not upper else 'PART_OF')
    return meronym_lca, round(time.perf_counter() - _start, 5)


def lca(_input: NeXSimResponse, _upper:bool=False):
    _start = time.perf_counter()
    computation_times = {
        "direct_instances": 0.0,
        "direct_part_of": 0.0,
        "subgraph_hypernyms": 0.0,
        "subgraph_meronyms": 0.0,
        "hypernym_lca": 0.0,
        "meronym_lca": 0.0
    }

    # Step 0: Retrieve direct instances
    raw_hypernyms, computation_times["direct_instances"] = compute_direct_instances(unit=_input.unit)
    direct_part_of, computation_times["direct_part_of"] = compute_direct_part_of(unit=_input.unit)

    # Step 1: Retrieve "subclass_of" subgraph
    hypernym_subgraph_result, computation_times["subgraph_hypernyms"] = compute_raw_subgraph_hypernyms_no_dummy_sg(
        unit=_input.unit,
        instances=raw_hypernyms)
    raw_hypernyms.extend(hypernym_subgraph_result)

    # Step 2: Hypernym LCA with "Clingo"
    # print("Starting clingo program for hypernyms...")

    hypernym_lca, computation_times["hypernym_lca"] = compute_hypernym_lca(unit=_input.unit,
                                                                           raw_hypernyms=raw_hypernyms,
                                                                           upper=_upper)

    # Step 3: Retrieve "part_of" subgraph

    raw_meronyms, computation_times["subgraph_meronyms"] = compute_raw_subgraph_meronyms_no_dummy_sg(unit=_input.unit,
                                                                                         direct_part_of=direct_part_of)

    # Step 4: Meronym LCA with "Clingo"
    # print("Starting clingo program for meronyms...")

    meronym_lca, computation_times["meronym_lca"] = compute_meronym_lca(unit=_input.unit,
                                                                        raw_meronyms=raw_meronyms,
                                                                        upper=_upper)

    computation_times["lca"] = round(time.perf_counter() - _start, 5)

    # Total lca is the union of hypernyms and meronyms lca
    _input.lca = hypernym_lca
    _input.lca.extend(meronym_lca)

    if _input.computation_times is None:
        _input.computation_times = {}

    for k in computation_times.keys():
        _input.computation_times[k] = computation_times[k]
