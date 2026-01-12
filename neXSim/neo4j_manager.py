from neo4j import GraphDatabase
import os

from neo4j.exceptions import Neo4jError, ServiceUnavailable, AuthError

from neXSim.models import Atom, EntityType

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
             "mainSense": record["mainSense"] if record["mainSense"] else "",
             "description": record["description"],
             "synonyms": record["synonyms"],
             "type": record["type"] if record['type'] else EntityType.NAMED_ENTITY}
            for record in result]


def search_by_lemma(tx, _lemma: str, _page: int = 0, _skip: int = 0):
    # lemma = remove_lucene_special_characters(_lemma)

    tokens = _lemma.split(" ")

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

    main_sense_str = f"({main_sense_str[:-5]})"
    synonyms_str = f"({synonyms_str[:-5]})"
    params_str = f"[{(params_str + params_str)[:-1]}]"

    if _page < 0:
        _page = 0

    skip = _page * 10



    query = """CALL db.index.fulltext.queryNodes("mainSensesAndSynonyms",
    apoc.text.format("{main_sense_str} OR {synonyms_str}", {params_str})) 
                    YIELD node, score WITH node, score 
                    ORDER BY score * node.undirected_edges DESC
                    RETURN node.id as id, 
                    node.mainSense as mainSense,
                    node.description as description,
                    node.synonyms as synonyms,
                    node.type as type 
                    SKIP {skip} LIMIT 10""".format(main_sense_str=main_sense_str,
                                                    synonyms_str=synonyms_str,
                                                    params_str=params_str,
                                                    lemma=_lemma,
                                                   skip=skip)
    result = tx.run(query, parameters=params)

    to_send = []

    for record in result:
        to_send.append({"id": record["id"],
             "mainSense": record["mainSense"] if record["mainSense"] else "",
             "description": record["description"],
             "synonyms": record["synonyms"],
             "type": record["type"] if record['type'] else EntityType.NAMED_ENTITY}
                   )


    return to_send

SUMMARY_QUERY = (

    """
    UNWIND $ids as _id 
    MATCH (a:Synset {{id:_id}})
    CALL {{
      WITH a
      MATCH (a)-[:{is_a}|{instance_of}]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "{is_a}" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:{subclass_of}*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "{is_a}" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:{instance_of}]->(mid)-[:{subclass_of}*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "{is_a}" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[:{part_of}*1..]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, "{part_of}" AS relation, b.id AS target
      UNION ALL
      WITH a
      MATCH (a)-[r]->(b:Synset)
      WHERE not type(r) in [
       "{instance_of}",
       "{subclass_of}",
       "{is_a}",
       "{part_of}" ]
      RETURN DISTINCT a.id as for, a.id AS source, type(r) AS relation, b.id AS target   
    }}
    RETURN DISTINCT for, source, relation, target;
    """
)


def compute_oneshot_summary(tx, _entities: list[str], _upper: bool = False):
    result = tx.run(SUMMARY_QUERY.format(is_a='IS_A' if _upper else 'is_a',
                                         subclass_of='SUBCLASS_OF' if _upper else 'subclass_of',
                                         instance_of='INSTANCE_OF' if _upper else 'instance_of',
                                         part_of='PART_OF' if _upper else 'part_of'), ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"],
             "for": record["for"]}
            for record in result]


SUBGRAPH_QUERY = """
WITH [{ids}] AS ids
UNWIND ids AS id
MATCH (s:Synset {{id:id}})
CALL apoc.path.subgraphAll(s, {{
  relationshipFilter: '{relation}>',
  uniqueness: 'RELATIONSHIP_GLOBAL',
  bfs: true
}}) YIELD relationships
UNWIND relationships AS r
WITH DISTINCT r
where type(r) = '{relation}'
RETURN DISTINCT startNode(r).id AS source, type(r) AS relation, endNode(r).id AS target;

"""


def compute_subgraph(tx, _to_attach: list[str], _relation: str, _upper: bool = False):
    ids = "'"
    ids += "','".join(_to_attach)
    ids += "'"
    if (((_upper and _relation == 'SUBCLASS_OF') or (_upper and _relation == 'PART_OF')) or
            ((not _upper and _relation == 'subclass_of') or (not _upper and _relation == 'part_of'))):
        inst_query = SUBGRAPH_QUERY.format(ids=ids, relation=_relation)
        result = tx.run(inst_query)
        return [{"source": record["source"],
                 "relation": record["relation"],
                 "target": record["target"]}
                for record in result]
    else:
        raise Exception(f"Subgraph not defined for relation {_relation}")


OTHERS_QUERY = (
    """
    UNWIND $ids AS _id
    MATCH (a:Synset {{id:_id}})-[r]->(b:Synset)
    WHERE not type(r) in [
       "{instance_of}",
       "{subclass_of}",
       "{is_a}",
       "{part_of}" ]]
    RETURN DISTINCT a.id AS source, type(r) AS relation, b.id AS target
    """
)


def compute_others(tx, _entities: str, _upper: bool = False):
    result = tx.run(OTHERS_QUERY.format(is_a='IS_A' if _upper else 'is_a',
                                        subclass_of='SUBCLASS_OF' if _upper else 'subclass_of',
                                        instance_of='INSTANCE_OF' if _upper else 'instance_of',
                                        part_of='PART_OF' if _upper else 'part_of'), ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"]}
            for record in result]


DIRECT_INSTANCES_QUERY = (
    """
    UNWIND $ids as _id 
    MATCH (a:Synset {{id:_id}})
    CALL {{
      WITH a
      MATCH (a)-[r:{names}]->(b:Synset)
      RETURN DISTINCT a.id as for, a.id AS source, type(r) AS relation, b.id AS target   
    }}
    RETURN for, source, relation, target;
    """
)


def compute_direct_instances(tx, _entities: list[str], names: list[str] = None, _upper: bool = False):
    if names is None:
        names = ['instance_of', 'is_a', 'subclass_of']
    if _upper:
        names = [x.upper() for x in names]
    _query = DIRECT_INSTANCES_QUERY.format(names="|".join(names))
    result = tx.run(_query, ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"],
             "type": "HYPERNYM"}
            for record in result]


def compute_direct_part_of(tx, _entities: list[str], names: list[str] = None, _upper: bool = False):
    if names is None:
        names = ['part_of']
    if _upper:
        names = [x.upper() for x in names]
    _query = DIRECT_INSTANCES_QUERY.format(names="|".join(names))
    result = tx.run(_query, ids=_entities)
    return [{"source": record["source"],
             "relation": record["relation"],
             "target": record["target"],
             "type": "MERONYM"}
            for record in result]


class DatasetManager(metaclass=SingletonMeta):
    DATABASE_ADDRESS = ""
    DATABASE_USERNAME = ""
    DATABASE_PASSWORD = ""

    def __init__(self) -> None:

        self.DATABASE_ADDRESS = os.environ.get('NEO4J_DB_URI')
        self.DATABASE_USERNAME = os.environ.get('NEO4J_DB_USER')
        self.DATABASE_PASSWORD = os.environ.get('NEO4J_DB_PWD')

        self.upper = os.environ.get('PREDICATES_UPPER', 'False').lower() == 'true'
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
        with self.driver.session() as session:
            return session.execute_read(search_by_lemma, _lemma=lemma, _page=page, _skip=skip)

    def get_direct_instances(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_direct_instances, _entities=_entities, _upper=self.upper)

    def get_direct_part_of(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_direct_part_of, _entities=_entities)

    def get_full_summary(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_oneshot_summary, _entities=_entities, _upper=self.upper)

    def get_raw_subclass(self, _entities: list[str], _direct_instances: list[Atom]):
        import copy
        _new = copy.deepcopy(_entities)
        for i in _direct_instances:
            if (self.upper and i.predicate == "INSTANCE_OF") or (not self.upper and i.predicate == "instance_of"):
                _new.append(i.target_id)
        with self.driver.session() as session:
            return session.write_transaction(compute_subgraph, _to_attach=_new,
                                             _relation="SUBCLASS_OF" if self.upper else "subclass_of",
                                             _upper=self.upper)

    def get_raw_part_of(self, _entities, _direct_instances):
        if len(_direct_instances) == 0:
            return []
        with self.driver.session() as session:
            return session.write_transaction(compute_subgraph, _to_attach=_entities,
                                             _relation="PART_OF" if self.upper else "part_of", _upper=self.upper)

    def get_others(self, _entities):
        with self.driver.session() as session:
            return session.execute_read(compute_others, _entities=_entities, _upper=self.upper)

    def clear_query_cache(self):
        with self.driver.session() as session:
            result = session.run("CALL db.clearQueryCaches()")
            return result

