from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from neXSim.neo4j_manager import DatasetManager
from neXSim.postgresQL_manager import PostgresQLConnector

load_dotenv()
neo4j_instance:DatasetManager = DatasetManager()
postgres_instance:PostgresQLConnector = PostgresQLConnector()
app = Flask(__name__)

CORS(app, supports_credentials=True)


from neXSim import router
