import os
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

def neo4j_connection() -> Neo4jGraph:
    """
    Establish a connection to the Neo4j database.

    Returns:
        Neo4jGraph: An instance of the Neo4jGraph class if the connection is successful, otherwise None.
    """
    try:
        graph = Neo4jGraph(
            url=os.environ['NEO4J_URI'],
            username=os.environ['NEO4J_USERNAME'],
            password=os.environ['NEO4J_PASSWORD']
        )
        logger.info("Successfully established Neo4j connection.")
        return graph
    except KeyError:
        logger.error("Environment variables for Neo4j connection are not set correctly.")
    except Exception as e:
        logger.error(f"Unexpected error during Neo4j connection establishment: {e}")
    return None