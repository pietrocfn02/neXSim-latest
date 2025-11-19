import os
import psycopg
from psycopg.rows import dict_row

from neXSim.utils import SingletonMeta

class PostgresQLConnector(metaclass=SingletonMeta):

    PG_DSN = ""

    def __init__(self):

        self.PG_DSN = os.environ.get('POSTGRES_DSN')

        if self.PG_DSN is None or self.PG_DSN == "":
            host = os.environ.get('POSTGRES_DB_HOSTNAME')
            db = os.environ.get('POSTGRES_DB_NAME')
            port = os.environ.get('POSTGRES_DB_PORT')
            user = os.environ.get('POSTGRES_DB_USERNAME')
            pwd = os.environ.get('POSTGRES_DB_PWD')

            self.PG_DSN = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


    def get_predicate_info(self, _identifier):
        sql = f"""
        SELECT p.name as name, p.short_name as short_name, p.symbol as symbol, p.type as type 
        from SYMBOL_TO_INTERNAL_IDENTIFIER i, PREDICATE_INFO p 
        where p.symbol = i.symbol 
        and i.internal_identifier = '{_identifier}'
        LIMIT 1"""

        with psycopg.connect(self.PG_DSN) as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute(sql, ())
                return cur.fetchall()

    def get_entities(self, _identifiers: list[str]):
        parameter = ""
        for _id in _identifiers:
            parameter += f"'{_id}',"
        parameter = parameter[:-1]
        sql =f""" SELECT s.* from synset s where s.id in ({parameter})"""
        with psycopg.connect(self.PG_DSN) as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute(sql, ())
                return cur.fetchall()