from neo4j import GraphDatabase

import ha.config as config


graphdb = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
