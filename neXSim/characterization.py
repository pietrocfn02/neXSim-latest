import copy
import time

from neXSim.models import Atom, BabelNetID, NeXSimResponse, Variable, Summary


def clean_strict_subsets(to_clean: list[set[str]]) -> list[set[str]]:
    to_return = copy.deepcopy(to_clean)
    for subset in to_clean:
        for other_subset in to_clean:
            if len(other_subset) < len(subset) and other_subset.issubset(subset):
                if other_subset in to_return:
                    to_return.remove(other_subset)
    return to_return


def maximal_intersection(l: list[set[str]],
                         r: list[set[str]]) -> list[set[str]]:
    intersection: list[set[str]] = []
    for left in l:
        for right in r:
            _int = left.intersection(right)
            if _int not in intersection:
                intersection.append(_int)
    return list(intersection)


def remove_if_covered_by_constants(source: list[set[str]],
                                   target: list[set[str]]) -> list[set[str]]:
    to_return: list[set[str]] = []
    for _set in source:
        if _set not in target:
            to_return.append(_set)
    return to_return


def to_relation_map(_to_parse: list[Atom], allowed_predicates: set[str]):
    parsed: dict[str, set[str]] = {}

    for atom in _to_parse:
        if atom.predicate in allowed_predicates:
            if atom.target_id not in parsed.keys():
                if isinstance(atom.target_id, str):
                    parsed[atom.target_id] = {atom.predicate}
                elif isinstance(atom.target_id, Variable):
                    parsed[str(atom.target_id)] = {atom.predicate}
            else:
                if isinstance(atom.target_id, str):
                    parsed[atom.target_id].add(atom.predicate)
                elif isinstance(atom.target_id, Variable):
                    parsed[str(atom.target_id)].add(atom.predicate)

    return parsed


def compute_pairwise_characterization(_left_operand: list[Atom],
                                      _right_operand: list[Atom],
                                      _free_variable: Variable) -> list[Atom]:
    # Since the summaries are transitively-closed outgoing edges,
    # we can state that for each atom p(a,b), a is ALWAYS the summarized entity
    # THIS IS AN ASSUMPTION for this specific algorithm

    # I'll take the intersection of predicates
    common_predicates = (set([x.predicate for x in _left_operand])
                         .intersection(set([x.predicate for x in _right_operand])))

    # I'll take the intersection of summaries
    common_summary = set(_left_operand).intersection(set(_right_operand))

    left_constant_map: dict[BabelNetID, set[str]] = to_relation_map(_left_operand, common_predicates)
    right_constant_map: dict[BabelNetID, set[str]] = to_relation_map(_right_operand, common_predicates)

    common_map: dict[BabelNetID, set[str]] = to_relation_map(list(common_summary), common_predicates)

    # now, no matter of the keys, I need just to know whether any of these
    # generated sets is associated with the strict subset of another
    # in this case, I will remove it

    left_candidate_variables: list[set[str]] = []
    for k in left_constant_map.keys():
        left_candidate_variables.append(left_constant_map[k])

    right_candidate_variables: list[set[str]] = []
    for k in right_constant_map.keys():
        right_candidate_variables.append(right_constant_map[k])

    common_values: list[set[str]] = []
    for k in common_map.keys():
        common_values.append(common_map[k])

    common_values = clean_strict_subsets(common_values)
    maximal_subsets: list[set[str]] = maximal_intersection(left_candidate_variables,
                                                           right_candidate_variables)
    maximal_subsets = clean_strict_subsets(maximal_subsets)
    variables: list[set[str]] = remove_if_covered_by_constants(maximal_subsets, common_values)

    bound_variables: list[Variable] = []

    noncommon_summary: list[Atom] = []

    # each element (set) in variables become a bound variable
    for _set in variables:
        v: Variable = Variable(is_free=False, origin=[], nominal=len(bound_variables))
        bound_variables.append(v)
        for p in _set:
            noncommon_summary.append(Atom(source_id=_free_variable, target_id=v, predicate=p))

    to_return: list[Atom] = list(common_summary)
    to_return.extend(noncommon_summary)

    return to_return


def compute_characterization(summaries):
    summaries = sorted(summaries)

    x: Variable = Variable(is_free=True,
                           origin=[tmp.entity for tmp in summaries if tmp is not None])

    # in each summary (in the copy), substitute the entity with the free variable
    new_summaries = []
    for s in summaries:
        e = s.entity
        tops = s.tops
        atoms: list[Atom] = []
        for atom in s.summary:
            tmp: Atom = atom
            if tmp.source_id == e:
                tmp = Atom(source_id=x, target_id=atom.target_id, predicate=atom.predicate)
            if tmp.target_id == e:
                tmp = Atom(source_id=atom.source_id, target_id=x, predicate=atom.predicate)
            atoms.append(tmp)
        new_summaries.append(Summary(entity=e, tops=tops, summary=atoms))

    if len(summaries) <= 1:
        raise Exception("You need at least two entities to characterize your unit")

    left_operand = new_summaries[0].summary

    new_summaries.pop(0)

    while len(new_summaries) > 0:
        right_operand = new_summaries[0].summary
        new_summaries.pop(0)

        left_operand = compute_pairwise_characterization(left_operand, right_operand, x)

    return left_operand


def characterize(_input: NeXSimResponse):
    _start = time.perf_counter()
    summaries = copy.deepcopy(_input.summaries)
    _input.characterization = compute_characterization(summaries)
    tops = set()
    for atom in _input.characterization:
        tops.add(str(atom.target_id))
        tops.add(str(atom.source_id))
    _input.tops = list(tops)
    if _input.computation_times is None:
        _input.computation_times = {"characterization": round(time.perf_counter() - _start, 5)}
    else:
        ct = _input.computation_times
        ct["characterization"] = round(time.perf_counter() - _start, 5)


# kernel explanation is a characterization-like explanation
# built on top of "summary tilde", which is essentially the summary minus the "hypernyms"/"meronyms"
# which are substituted with the LCAs
def kernel_explanation(_input: NeXSimResponse):
    _start = time.perf_counter()
    summary_tilde: list[Summary] = []
    for summary in _input.summaries:
        entity = summary.entity
        tmp_tops: set[str] = set()
        tmp_atoms: list[Atom] = []
        constants_to_names: dict[BabelNetID, set[str]] = {}
        for atom in summary.summary:
            if atom.target_id not in constants_to_names:
                constants_to_names[atom.target_id] = set()
            constants_to_names[atom.target_id].add(atom.predicate)
            if atom.predicate.lower() not in ['is_a', 'instance_of', 'subclass_of', 'part_of']:
                tmp_atoms.append(atom)
                tmp_tops.add(atom.source_id)
                tmp_tops.add(atom.target_id)

        for atom in _input.lca:
            tmp_atoms.append(Atom(source_id=entity, target_id=atom.target_id, predicate=atom.predicate))
            tmp_tops.add(atom.target_id)

        for constant in constants_to_names.keys():
            if (len(constants_to_names[constant]) > 1
                    and ('IS_A' in constants_to_names[constant] or 'is_a' in constants_to_names[constant])):
                tmp_atoms.append(Atom(source_id=entity,
                                      target_id=constant,
                                      predicate='IS_A' if 'IS_A' in constants_to_names[constant] else 'is_a'))
                tmp_tops.add(constant)
            if (len(constants_to_names[constant]) > 1
                    and ('PART_OF' in constants_to_names[constant] or 'part_of' in constants_to_names[constant])):
                tmp_atoms.append(Atom(source_id=entity,
                                      target_id=constant,
                                      predicate='PART_OF' if 'PART_OF' in constants_to_names[constant] else 'part_of'))
                tmp_tops.add(constant)

        summary_tilde.append(Summary(entity=summary.entity, tops=list(tmp_tops), summary=tmp_atoms))

    _input.kernel_explanation = compute_characterization(summary_tilde)

    if _input.computation_times is None:
        _input.computation_times = {"ker": round(time.perf_counter() - _start, 5)}
    else:
        ct = _input.computation_times
        ct["ker"] = round(time.perf_counter() - _start, 5)


# the characterization obtained via "direct product" of summaries
def canonical_characterization(_input: NeXSimResponse):
    pass
