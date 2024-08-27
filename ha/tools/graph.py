import json
import logging

from ha import config
from ha.agent.executor import QueryExecutor
from ha.models import openai_client as client
from ha.neo4j import graphdb
from ha.tools.kegg import kegg_tips
from ha.utils import clean_markdown_response

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set logging level to ERROR or higher to ignore WARNING messages
logging.getLogger("neo4j").setLevel(logging.ERROR)


class GraphAnalysis(QueryExecutor):

    NAME = "Graph Analysis Query Executor"

    def __init__(self, model: str = config.OPENAI_NEO4J_MODEL, attempts: int = 5):
        super().__init__(model, attempts)

    def generate_query(self, instruction: str, goal_template: str, reflection: str, schema: str,
                       tips: str = kegg_tips) -> tuple:
        """
        Method generates the right .

        Args:
            instruction: The user's request.
            goal_template: The goal template for the query.
            reflection: The user's reflection on the previous response.
            schema: The Neo4j schema.
            tips: The tips to provide to the assistant.

        Returns:
            The generated network analysis parameters (gene symbol and ) and explanation.
        """
        prompt = (f"Given this instruction: {instruction}\n"
                  f"Choose from the available pathways: {self.get_all_pathways()}\n" # this is a bit of a cheat
                  f"Generate the following JSON object: "
                  f"{{\"node_name\": \"<a gene symbol e.g. INSR>\", "
                  f"\"pathway_title\": \"<the exact name of the KEGG pathway; recommended: query for it before hand>\""
                  f"\"explanation\": \"<explanation>\"}}\n")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates queries using JSON template."
                                              "{'node_name': '<node_name>', 'pathway_title': '<pathway_title>', "
                                              "'explanation': '<explanation>'}."
                                              "You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        try:
            jsn = json.loads(clean_markdown_response(response.choices[0].message.content))
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            raise ValueError(f"Failed to decode JSON response from {self.model}. Response: {response}")
        logger.info(f"I've found the following target node and pathway: {jsn['node_name']} in {jsn['pathway_title']}")
        return jsn, jsn['explanation']

    def execute_query(self, query: dict) -> dict:
        """
        Provides an analysis of a node in a pathway graph through a set of metrics based on the graph structure.

        - forest_subarea_ratio: ratio indicating the potential impact of a node on a specific pathway.

        - root_to_node: the minimum/maximum distance between a root of the pathway and the chosen node;
        another metric that shows the potential impact of the node on the pathway.

        - node_to_leaf: the minimum distance between the chosen node and any leaf below the node;
        illustrates the intensity of impact assuming changes closer to a terminal node (a leaf) have more direct effect.

        - root_to_leaf: the minimum distance between the root of the pathway and any leaf below the node;
        mostly provides context about the pathway and how efficient activating the node could be.

        - directly_impacted_nodes: a list of nodes (gene symbols) that are directly impacted by the given node in the pathway.
        """
        node_name = query['node_name']
        pathway_title = query['pathway_title']
        return {
            'node_name': node_name,
            'pathway_title': pathway_title,
            'forest_subarea_ratio': self.forest_subarea_ratio(node_name, pathway_title),
            **self.root_and_leaf_distances(node_name, pathway_title),
            'directly_impacted_nodes': self.get_directly_impacted_nodes(node_name, pathway_title),
            'note on forest subarea ratio': 'The forest subarea ratio is a metric that indicates '
                                            'the potential impact of a node on a specific pathway. '
                                            'It is calculated as the ratio between nodes in the subtree of a node '
                                            'that pertain to a specific pathway compared to all nodes in the graph '
                                            'of the same pathway.',
        }

    def generate_response(self, instructions: str, goal_template: str, reflection: str, query_response: str) -> str:
        """
        A stub; just returns the query response.

        Args:
            instructions: The instructions for the query.
            goal_template: The goal template for the query.
            reflection: The reflection on the query response.
            query_response: The query response.

        Returns:
            The response to the query.
        """
        return query_response

    @staticmethod
    def forest_subarea_ratio(node_name: str, pathway_title: str) -> float:
        """
        Calculates the ratio between nodes in the subtree of a node that pertain to a specific pathway compared to all
        nodes in the graph of the same pathway.

        The goal of this method is to provide a metric that indicates the potential impact of a node on a specific
        pathway.

        Args:
            node_name: The name of the node.
            pathway_title: The title of the pathway.

        Returns:
            forest subarea ratio: ratio indicating the potential impact of a node on a specific pathway.
        """
        with graphdb.session() as session:
            result = session.run(
                """
                MATCH (root {name: $node_name})-[:CHILD_OF*0..]->(descendant)
                WHERE $pathway_title IN descendant.pathway_titles
                WITH count(descendant) AS subtreeNodes
                MATCH (n)
                WHERE $pathway_title IN n.pathway_titles
                WITH subtreeNodes, count(n) AS totalNodes
                RETURN subtreeNodes * 1.0 / totalNodes AS forest_subarea_ratio
                """,
                node_name=node_name, pathway_title=pathway_title).single()
            if not result:
                logger.error(f"No result found for forest_subarea_ratio calculation for {node_name} in {pathway_title}.")
                return 0.0
            return result['forest_subarea_ratio']

    @staticmethod
    def get_root_depths(pathway_title) -> dict:
        """
        Calculates the minimum and maximum distances between the root of the pathway and any leaf below the node.

        Args:
            pathway_title: The title of the pathway.

        Returns:
            A dictionary containing the minimum and maximum distances between the root of the pathway and any leaf below the node.
        """
        # Cypher query to find min and max distances
        query = """
        MATCH (n)
        WHERE $pathway_title IN n.pathway_titles
        AND NOT ()-->(n)  // Ensure n is a root node
        AND (n)--()       // Exclude singleton nodes
        
        MATCH path = (n)-[*]->(leaf)
        WHERE NOT (leaf)-->()  // Ensure leaf is a leaf node
        AND all(node in nodes(path) WHERE $pathway_title IN node.pathway_titles)

        RETURN MIN(length(path)) AS min_distance, MAX(length(path)) AS max_distance
        """

        # Execute the query using the neo4j driver
        with graphdb.session() as session:
            return session.run(query, pathway_title=pathway_title).single()

    @staticmethod
    def get_node_subtree_depths(node_name, pathway_title) -> dict:
        """
        Calculates the minimum and maximum distances between the root of the pathway and any leaf below the node.

        Args:
            node_name: The name of the node.
            pathway_title: The title of the pathway.

        Returns:
            A dictionary containing the minimum and maximum distances between the root of the pathway and any leaf below the node.
        """

        # Cypher query to find min and max distances
        query = """
            MATCH (n)
            WHERE n.name = $node_name AND $pathway_title IN n.pathway_titles

            MATCH path = (n)-[*]->(leaf)
            WHERE NOT (leaf)-->()  // Ensure leaf is a leaf node
            AND all(node in nodes(path) WHERE $pathway_title IN node.pathway_titles)

            RETURN MIN(length(path)) AS min_distance, MAX(length(path)) AS max_distance
            """

        # Execute the query using the neo4j driver
        with graphdb.session() as session:
            return session.run(query, node_name=node_name, pathway_title=pathway_title).single()

    @staticmethod
    def get_roots_to_node_distances(node_name: str, pathway_title: str) -> dict:
        """
        Calculates the minimum and maximum distances between a root of the pathway and the chosen node.

        Args:
            node_name: The name of the node.
            pathway_title: The title of the pathway.

        Returns:
            A dictionary containing the minimum and maximum distances between the root of the pathway and the chosen node.
        """
        # Cypher query to find min and max distances
        query = """
            MATCH (target)
            WHERE target.name = $node_name
            AND $pathway_title IN target.pathway_titles
            
            WITH target
            
            MATCH (root)
            WHERE NOT ()-[*]->(root) 
            AND $pathway_title IN root.pathway_titles
            
            WITH root, target
            MATCH path = shortestPath((root)-[*]->(target))
            WHERE target <> root AND all(n IN nodes(path) WHERE $pathway_title IN n.pathway_titles)
            RETURN min(length(path)) AS min_distance, max(length(path)) AS max_distance
            """

        # Execute the query using the neo4j driver
        with graphdb.session() as session:
            return session.run(query, node_name=node_name, pathway_title=pathway_title).single()

    def root_and_leaf_distances(self, node_name: str, pathway_title: str) -> dict:
        """
        Calculates a few metrics based on distances between a chosen node, the root(s) of the current pathway above
        the node, and the leaves of the pathway below the node.
        - root_to_node: depth measured from any root to the node
        - node_to_leaf: depth measured from the node to any leaf
        - root_to_leaf: depth measured from any root to any leaf below the node
        """
        root_to_node = self.get_roots_to_node_distances(node_name, pathway_title)
        node_to_leaf = self.get_node_subtree_depths(node_name, pathway_title)
        root_to_leaf = self.get_root_depths(pathway_title)

        return {
            'root_to_node': root_to_node,
            'node_to_leaf': node_to_leaf,
            'root_to_leaf': root_to_leaf
        }

    @staticmethod
    def get_directly_impacted_nodes(node_name: str, pathway_title: str) -> list:
        """
        Returns the nodes that are directly impacted by the given node in the pathway.

        Args:
            node_name: The name of the node.
            pathway_title: The title of the pathway.

        Returns:
            A list of nodes that are directly impacted by the given node in the pathway.
        """
        #TODO: NOTE -- unsure if this is needed at this point.

        # Cypher query to find directly impacted nodes
        query = """
            MATCH (n)
            WHERE n.name = $node_name
            WITH n
            MATCH (n)-[r]->(child)
            WHERE $pathway_title IN child.pathway_titles
            RETURN child.name AS directly_impacted_node
            """
        # Execute the query using the neo4j driver
        with graphdb.session() as session:
            result = session.run(query, node_name=node_name, pathway_title=pathway_title)
            # Extract the 'directly_impacted_node' values from the result
            return [record['directly_impacted_node'] for record in result]

    @staticmethod
    def get_all_pathways() -> str:
        """
        Retrieves all KEGG pathways from the Neo4j database.

        Returns:
            A list of all KEGG pathways.
        """
        with graphdb.session() as session:
            results = session.run("MATCH (p:Pathway) RETURN p.title AS pathway_title")
            return '"' + '", "'.join([record['pathway_title'] for record in results]) + '"'
