from neXSim.models import NeXSimResponse, Entity, Atom, Variable
from neXSim.search import search_by_id
from neXSim.lca import lca, compute_raw_subgraph_hypernyms, compute_raw_subgraph_meronyms, compute_direct_instances
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
    if _input.unit is None or len(_input.unit) == 0:
        return "Empty unit!"
    print(1)
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
    print(1.5)
    _involved_entities: set[Entity] = set(_entities)
    _involved_entities = _involved_entities.union(search_by_id(list(_ids_in_summaries)))
    print(1.8)
    for summary in _input.summaries:
        _output += f"Summary for {entity_to_outfile(find_entity_from_list(summary.entity, _entities))}: \n"
        print(1.9)
        print(len(summary.summary))
        i = 1
        for atom in summary.summary:
            print(f"{i} of {len(summary.summary)}")
            _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
            i += 1
        _output += "\n"
    print(2)
    if _input.lca is None:
        lca(_input)

    _output += "LCA: \n"
    for atom in _input.lca:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"

    direct_instances: list[Atom] = compute_direct_instances(_input.unit)[0]
    raw_subgraph_hypernyms: list[Atom] = compute_raw_subgraph_hypernyms(_input.unit, direct_instances)[0]
    raw_subgraph_meronyms: list[Atom] = compute_raw_subgraph_meronyms(_input.unit)[0]
    print(3)
    _output += "Direct Instances: \n"
    for direct_instance in direct_instances:
        _output += f"{atom_to_outfile(direct_instance, _involved_entities)}\n"
    print(4)
    _output += "Raw Subgraph Hypernyms: \n"
    print(len(raw_subgraph_hypernyms))
    for h in raw_subgraph_hypernyms:
        # new: set[str] = set()
        #if h.source_id not in _ids_in_summaries and h.source_id not in new:
        #    new.add(h.source_id)
        #if h.target_id not in _ids_in_summaries and h.target_id not in new:
        #    new.add(h.target_id)
        #_involved_entities = _involved_entities.union(search_by_id(list(new)))
        #_ids_in_summaries.union(new)
        _output += f"{atom_to_outfile(h, _involved_entities)}\n"
    print(5)
    _output += "Raw Subgraph Meronyms: \n"
    print(len(raw_subgraph_meronyms))
    for m in raw_subgraph_meronyms:
    #    new: set[str] = set()
    #    if m.source_id not in _ids_in_summaries and m.source_id not in new:
    #        new.add(m.source_id)
    #    if m.target_id not in _ids_in_summaries and m.target_id not in new:
    #        new.add(m.target_id)
    #    _involved_entities = _involved_entities.union(search_by_id(list(new)))
    #    _ids_in_summaries.union(new)
        _output += f"{atom_to_outfile(m, _involved_entities)}\n"
    print(6)
    if _input.characterization is None:
        characterize(_input)

    _output += "Characterization: \n"
    for atom in _input.characterization:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"
    print(7)
    if _input.kernel_explanation is None:
        kernel_explanation(_input)

    _output += "Kernel Explanation: \n"
    for atom in _input.kernel_explanation:
        _output += f"{atom_to_outfile(atom, _involved_entities)}\n"
    _output += "\n"
    print(8)
    if _input.computation_times is not None:
        _output += "###############################\n"
        _output += "Computation Times: \n"
        for entry in _input.computation_times.keys():
            _output += f"{entry}: {_input.computation_times[entry]} s\n"
        _output += "###############################"
    return _output
