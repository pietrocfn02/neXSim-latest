import time

from neXSim.models import NeXSimResponse, Entity, Atom, Variable
from neXSim.search import search_by_id
from neXSim.lca import lca
from neXSim.summary import full_summary
from neXSim.characterization import characterize, kernel_explanation


def find_entity_from_list(to_find: str, collection: set[Entity]) -> Entity | str:
    for entity in collection:
        if entity.id == to_find:
            return entity
    # tmp: set[Entity] = search_by_id([to_find])
    # if len(tmp) > 0:
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
    if _input.summaries is None or len(_input.summaries) == 0:
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

    if _input.lca is None or len(_input.lca) == 0:
        lca(_input)

    _output += "LCA: \n"
    for atom in _input.lca:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"

    if _input.characterization is None or len(_input.characterization) == 0:
        characterize(_input)

    _output += "Characterization: \n"
    for atom in _input.characterization:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"

    if _input.kernel_explanation is None or len(_input.kernel_explanation) == 0:
        kernel_explanation(_input)

    _output += "Kernel Explanation: \n"
    for atom in _input.kernel_explanation:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"
    _total = round(time.perf_counter() - _start, 5)
    if _input.computation_times is not None:
        ct = _input.computation_times
        _output += "###############################\n"
        _output += "Computation Times: \n"
        for entry in ct.keys():
            _output += f"{entry}: {ct[entry]} s\n"
        _output += f"Total Clock Time: {_total} s\n"
        _output += f"Total Core Time: {round(ct['summary'] + ct['characterization'], 5)} s\n"
        _output += f"Total Ker Time: {round(ct['summary'] + ct['lca'] + ct['ker'],5)} s\n"
        _output += "###############################"
    return _output
