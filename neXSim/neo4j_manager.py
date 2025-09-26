from neo4j import GraphDatabase
import os

from neo4j.exceptions import Neo4jError, ServiceUnavailable, AuthError

from neXSim.models import Atom

DATABASE_ADDRESS = ""
DATABASE_NAME = ""
DATABASE_PASSWORD = ""

from neXSim.utils import SingletonMeta


def search_by_id(tx, _identifiers: list[str]):
    query = """
    MATCH (x:Synset)
    WHERE x.id IN $ids
    RETURN x.id as id,
    x.mainSense as mainSense,
    x.description as description,
    x.synonyms as synonyms,
    x.type as type
    """
    result = tx.run(query, ids=_identifiers)
    return [{"id": record["id"],
             "main_sense": record["mainSense"],
             "description": record["description"],
             "synonyms": record["synonyms"],
             "type": record["type"]}
            for record in result]


"""
def remove_lucene_special_characters(lemma):
    lucene_special_characters = r'+-!(){}[]<>/^"~*?:\\'
    escaped_query = re.sub(r'([{}])'.format(re.escape(lucene_special_characters)), '', lemma)
    return escaped_query

def get_synset_by_lemma_query(tx, _lemma: str, _page: int = 0) -> list[Entity]:
    lemma = remove_lucene_special_characters(_lemma)
    tokens = lemma.split(" ")

    if len(tokens) == 0:
        return []

    params = {}
    count_lemma = 0
    main_sense_str = ""
    synonyms_str = ""
    params_str = ""

    for token in tokens:
        if token == "":
            continue

        params[f"l{count_lemma}"] = token
        params_str += f"$l{count_lemma},"
        count_lemma += 1

        main_sense_str += "main_sense:%s* AND "
        synonyms_str += "synonyms:%s AND "

    main_sense_str = f"({main_sense_str[:-5]})^3"
    synonyms_str = f"({synonyms_str[:-5]})"
    params_str = f"[{(params_str + params_str)[:-1]}]"

    if page < 0:
        page = 0

    skip = page * 10

    result = tx.run(f\"""CALL db.index.fulltext.queryNodes("mainSensesAndSynonyms", 
    apoc.text.format("{main_sense_str} OR {synonyms_str}", {params_str})) YIELD node,
                     score WITH node, score ORDER BY node.num_rel*score DESC, node.id 
                    RETURN node.id as id, node.main_sense as main_sense, node.synonyms as synonyms, 
                    node.description as description, node.image_url as image_url SKIP {skip} LIMIT 10""\"
                    , parameters=params)

    entities = []

    for record in result:
        print(record)
    return entities

"""

SUMMARY_QUERY = (
    """
    UNWIND $ids as _id 
    MATCH (a:Synset {id:_id})
    CALL {
      WITH a
      MATCH (a)-[:is_a|instance_of]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "is_a" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:subclass_of*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "is_a" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:instance_of]->(mid)-[:subclass_of*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "is_a" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:part_of*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "part_of" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[r]->(b:Synset)
      WHERE type(r) <> "instance_of" and type(r) <> "subclass_of" and type(r) <> "is_a" and type(r) <> "part_of"
      RETURN DISTINCT a.id as for, a.id AS source, type(r) AS relation, b.id AS target   
    }
    RETURN for, source, relation, target;
    """
)


def compute_oneshot_summary(tx, _entities: list[str]):
    result = tx.run(SUMMARY_QUERY, ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"],
             "for": record["for"]}
            for record in result]


HYPERNYM_SUBGRAPH_QUERY = """
CREATE (dummy:Dummy)
WITH dummy, $ids AS ids

// Subquery: compute results (may be empty)
CALL {
  WITH dummy, ids
  UNWIND ids AS _id 
    MATCH (e:Synset {id:_id})
    MERGE (dummy)-[:x]->(e)
  WITH dummy
  CALL apoc.path.subgraphAll(dummy,
    { uniqueness:'RELATIONSHIP_GLOBAL',
      relationshipFilter:'x>|subclass_of>' }) 
  YIELD relationships
  UNWIND relationships AS r
  WITH startNode(r) AS s, endNode(r) AS t, type(r) AS arc
  WHERE arc = 'subclass_of'
  RETURN collect({source:s.id, relation:arc, target:t.id}) AS results
}
WITH dummy, coalesce(results, []) AS results

// Delete always runs, because dummy is still bound here
DETACH DELETE dummy
RETURN results
"""

MERONYM_SUBGRAPH_QUERY = """
CREATE (dummy:Dummy)
WITH dummy, $ids AS ids

// Subquery: compute results (may be empty)
CALL {
  WITH dummy, ids
  UNWIND ids AS _id 
    MATCH (e:Synset {id:_id})
    MERGE (dummy)-[:x]->(e)
  WITH dummy
  CALL apoc.path.subgraphAll(dummy,
    { uniqueness:'RELATIONSHIP_GLOBAL',
      relationshipFilter:'x>|part_of>' }) 
  YIELD relationships
  UNWIND relationships AS r
  WITH startNode(r) AS s, endNode(r) AS t, type(r) AS arc
  WHERE arc = 'part_of'
  RETURN collect({source:s.id, relation:arc, target:t.id}) AS results
}
WITH dummy, coalesce(results, []) AS results

// Delete always runs, because dummy is still bound here
DETACH DELETE dummy
RETURN results
"""


def compute_subgraph(tx, _to_attach: list[str], _relation: str):
    if _relation == "subclass_of":
        result = tx.run(HYPERNYM_SUBGRAPH_QUERY, ids=_to_attach)
        print(_to_attach)
    elif _relation == "part_of":
        result = tx.run(MERONYM_SUBGRAPH_QUERY, ids=_to_attach)
    else:
        raise Exception(f"Subgraph not defined for relation {_relation}")
    outlist = []
    for record in result:
        for tmp in record["results"]:
            outlist.append({
                "source": tmp["source"],
                "relation": tmp["relation"],
                "target": tmp["target"]
            })
    return outlist


OTHERS_QUERY = (
    """
    UNWIND $ids AS _id
    MATCH (a:Synset {id:_id})-[r]->(b:Synset)
    WHERE not type(r) in ['instance_of', 'subclass_of', 'is_a', 'part_of']
    RETURN DISTINCT a.id AS source, type(r) AS relation, b.id AS target
    """
)


def compute_others(tx, _entities: str):
    result = tx.run(OTHERS_QUERY, ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"]}
            for record in result]


DIRECT_INSTANCES_QUERY = (
    """
    UNWIND $ids as _id 
    MATCH (a:Synset {id:_id})
    CALL {
      WITH a
      MATCH (a)-[:instance_of]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "instance_of" AS relation, b.id AS target   
    }
    RETURN for, source, relation, target;
    """
)


def compute_direct_instances(tx, _entities: list[str]):
    result = tx.run(DIRECT_INSTANCES_QUERY, ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"],
             "type": "OTHER"}
            for record in result]


class DatasetManager(metaclass=SingletonMeta):
    DATABASE_ADDRESS = ""
    DATABASE_USERNAME = ""
    DATABASE_PASSWORD = ""

    def __init__(self) -> None:

        self.DATABASE_ADDRESS = os.environ.get('NEO4J_DB_URI')
        self.DATABASE_USERNAME = os.environ.get('NEO4J_DB_USER')
        self.DATABASE_PASSWORD = os.environ.get('NEO4J_DB_PWD')

        assert (self.DATABASE_ADDRESS != "" and self.DATABASE_USERNAME != "" and self.DATABASE_PASSWORD != "")

        self.driver = GraphDatabase.driver(self.DATABASE_ADDRESS, auth=(self.DATABASE_USERNAME, self.DATABASE_PASSWORD))
        try:
            self.driver.verify_connectivity()
        except (ServiceUnavailable, AuthError, Neo4jError):
            print("Neo4j driver connection failed")
            self.driver.close()
            self.driver = None

    def get_entities(self, _id):
        with self.driver.session() as session:
            return session.execute_read(search_by_id, _identifiers=_id)

    def get_entities_by_lemma(self, lemma, page, skip):
        pass
        # with self.driver.session() as session:
        # return session.execute_read(search_by_lemma, _lemma=lemma, _page=page, _skip=skip)

    def get_direct_instances(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_direct_instances, _entities=_entities)

    def get_full_summary(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_oneshot_summary, _entities=_entities)

    def get_raw_subclass(self, _entities: list[str], _direct_instances: list[Atom]):
        import copy
        _new = copy.deepcopy(_entities)
        for i in _direct_instances:
            _new.append(i.target_id)
        with self.driver.session() as session:
            return session.execute_write(compute_subgraph, _to_attach=_new, _relation="subclass_of")

    def get_raw_part_of(self, _entities):
        with self.driver.session() as session:
            return session.execute_write(compute_subgraph, _to_attach=_entities, _relation="part_of")

    def get_others(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_others, _entities=_entities)
