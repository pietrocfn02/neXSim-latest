import time

from neXSim.models import NeXSimResponse, Atom, Summary
from neXSim import DatasetManager


def full_summary(_input: NeXSimResponse):
    _start = time.perf_counter()
    entities = _input.unit
    d: DatasetManager = DatasetManager()
    _summary_entries: dict[str, list[Atom]] = {}
    _tops: dict[str, set[str]] = {}
    neo4j_result = d.get_full_summary(entities)
    for entity in entities:
        _summary_entries[entity] = []
        _tops[entity] = set()
    for r in neo4j_result:
        _tops[r["for"]].add(r["target"])
        _summary_entries[r["for"]].append(Atom(source_id=r["source"],
                                                  target_id=r["target"],
                                                  predicate=r["relation"]))
    for entity in entities:
        _input.summaries.append(Summary(entity=entity,
                                        summary=_summary_entries[entity],
                                        tops=list(_tops[entity])))

    if _input.computation_times is None:
        _input.computation_times = {"summary": round(time.perf_counter() - _start, 5)}
    else:
        _input.computation_times["summary"] = round(time.perf_counter() - _start, 5)
