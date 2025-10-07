import time

from neXSim.models import NeXSimResponse, Entity, Atom, Variable
from neXSim.search import search_by_id
from neXSim.lca import lca, compute_raw_subgraph_hypernyms, compute_raw_subgraph_meronyms, compute_direct_instances, \
    compute_direct_part_of
from neXSim.summary import full_summary
from neXSim.characterization import characterize, kernel_explanation


def find_entity_from_list(to_find: str, collection: set[Entity]) -> Entity | str:
    for entity in collection:
        if entity.id == to_find:
            return entity
    #tmp: set[Entity] = search_by_id([to_find])
    #if len(tmp) > 0:
    #    for entity in tmp:
    #        return entity
    return to_find

def entity_to_outfile(e: Entity | str) -> str:
    if isinstance(e, Entity):
        return f'"{e.main_sense}[{e.id}]"' if e.main_sense else f'"{e.id}"'
    return e


def atom_to_outfile(atom: Atom, involved: set[Entity]) -> str:
    p = atom.predicate
    s = ""
    t = ""
    if type(atom.source_id) == str:
        s = entity_to_outfile(find_entity_from_list(atom.source_id, involved))
    elif type(atom.source_id) == Variable:
        s = str(atom.source_id)

    if type(atom.target_id) == str:
        t = entity_to_outfile(find_entity_from_list(atom.target_id, involved))
    elif type(atom.target_id) == Variable:
        t = str(atom.target_id)

    return f"{p}({s},{t})"


def report_all(_input: NeXSimResponse) -> str:
    _start = time.perf_counter()
    if _input.unit is None or len(_input.unit) == 0:
        return "Empty unit!"
    _output = "Unit: "
    _entities: set[Entity] = search_by_id(_input.unit)
    for _entity in _entities:
        _output += entity_to_outfile(_entity) + ", "
    _output = _output[:-2] + "\n \n"
    if _input.summaries is None:
        full_summary(_input)
    _ids_in_summaries: set[str] = set()
    for summary in _input.summaries:
        for top in summary.tops:
            if top not in _input.unit:
                _ids_in_summaries.add(top)

    _involved_entities: set[Entity] = set(_entities)
    _involved_entities = _involved_entities.union(search_by_id(list(_ids_in_summaries)))

    for summary in _input.summaries:
        _output += f"Summary for {entity_to_outfile(find_entity_from_list(summary.entity, _entities))}: \n"
        for atom in summary.summary:
            _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
        _output += "\n"
    if _input.lca is None:
        lca(_input)

    _output += "LCA: \n"
    for atom in _input.lca:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"

    direct_instances: list[Atom] = compute_direct_instances(_input.unit)[0]
    direct_part_of: list[Atom] = compute_direct_part_of(_input.unit)[0]
    raw_subgraph_hypernyms: list[Atom] = compute_raw_subgraph_hypernyms(_input.unit, direct_instances)[0]
    raw_subgraph_meronyms: list[Atom] = compute_raw_subgraph_meronyms(_input.unit, direct_part_of)[0]
    _output += "Direct Instances: \n"
    for direct_instance in direct_instances:
        _output += f"{atom_to_outfile(direct_instance, _involved_entities)}\n"
    _output += "Raw Subgraph Hypernyms: \n"
    for h in raw_subgraph_hypernyms:
        _output += f"{atom_to_outfile(h, _involved_entities)}\n"

    _output += "Raw Subgraph Meronyms: \n"
    for m in raw_subgraph_meronyms:
        _output += f"{atom_to_outfile(m, _involved_entities)}\n"

    if _input.characterization is None:
        characterize(_input)

    _output += "Characterization: \n"
    for atom in _input.characterization:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"

    if _input.kernel_explanation is None:
        kernel_explanation(_input)

    _output += "Kernel Explanation: \n"
    for atom in _input.kernel_explanation:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"
    _total = time.perf_counter() - _start
    if _input.computation_times is not None:
        _output += "###############################\n"
        _output += "Computation Times: \n"
        for entry in _input.computation_times.keys():
            _output += f"{entry}: {_input.computation_times[entry]} s\n"
        _output += f"Total Computation Time: {_total} s\n"
        _output += "###############################"
    return _output
