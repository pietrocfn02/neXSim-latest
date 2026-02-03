from neXSim.models import Entity
from neXSim import neo4j_instance, postgres_instance


def parse_entity(e):
    _id = e["id"]

    if "mainSense" in e.keys():
        _main_sense = e["mainSense"] if e["mainSense"] is not None else ""
    elif "main_sense" in e.keys():
        _main_sense = e["main_sense"] if e["main_sense"] is not None else ""
    else:
        _main_sense = ""

    _synonyms = e["synonyms"]
    _description = e["description"] if e["description"] is not None else ""

    if "type" in e.keys():
        _type = e["type"] if e["type"] is not None else "NAMED_ENTITY"
    elif "synset_type" in e.keys():
        _type = e["synset_type"] if e["synset_type"] is not None else "NAMED_ENTITY"
    else:
        _type = "NAMED_ENTITY"

    _image_url = e["image_url"] if e["image_url"] is not None else ""

    tmp: Entity = Entity(id=_id, main_sense=_main_sense, entity_type=_type,
                         description=_description, synonyms=_synonyms, image_url=_image_url)

    return tmp

def result_to_entity_list(result) -> list[Entity]:

    entities = []
    for entity in result:
        entities.append(parse_entity(entity))

    return entities


def result_to_entity_set(result) -> set[Entity]:
    result_set: set[Entity] = set()
    if result is None:
        return result_set
    for e in result:
        result_set.add(parse_entity(e))
    return result_set


def search_by_id(identifiers: list[str], on_graph: bool = True) -> set[Entity]:
    if on_graph:
        return result_to_entity_set(neo4j_instance.get_entities(identifiers))
    return result_to_entity_set(postgres_instance.get_entities(identifiers))


def search_by_lemma(lemma: str, page: int = 0, skip: int = 0) -> list[Entity]:
    return result_to_entity_list(neo4j_instance.get_entities_by_lemma(lemma, page, skip))
