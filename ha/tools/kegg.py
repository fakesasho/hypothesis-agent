import json
import logging
from typing import Union, Dict, List

from neo4j.exceptions import CypherSyntaxError, CypherTypeError

from ha.agent.executor import QueryExecutor
from ha.models import openai_client as client
from ha.neo4j import graphdb
from ha import config
from ha.utils import generative_execution, clean_markdown_response

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


kegg_tips = """
- use the `pathway_titles` attribute (a list) to filter for diseases
- don't be overly specific with the query
- use lower case when trying to match names, e.g. toLower(toString(x)) = 'cancer'
- always use toString() when making string comparison operations or matching
- can you normalise names and terms in the instructions?
- can you use alternative names or synonyms of terms in the instructions?
- if there is a single or a double quote in the search string, escape it with a backslash
"""


class Kegg(QueryExecutor):

    NAME = "KEGG Query Executor"

    def __init__(self, model=config.OPENAI_NEO4J_MODEL, attempts: int = 5):
        super().__init__(model, attempts)


    @generative_execution
    def generate_query(self, instruction: str, goal_template: str, reflection: str, schema: str,
                       tips: str = kegg_tips) -> tuple:
        """
        Method that uses OpenAI to generate a Neo4j query given a Neo4j schema and a request.

        Args:
            instruction: The user's request.
            goal_template: The goal template for the query.
            reflection: The user's reflection on the previous response.
            schema: The Neo4j schema.
            tips: The tips to provide to the assistant.

        Returns:
            The generated Neo4j query and explanation.
        """
        prompt = (f"Given the following Neo4j schema:\n{schema}\n"
                  f"Use this reflection {reflection}\n"
                  f"And these tips: {tips}\n"
                  f"Take into account the goal data template if relevant: {goal_template}"
                  f"Generate a Neo4j query that satisfies this instruction: {instruction}")

        # Send the image and text prompt to GPT-4 with Vision
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates queries using JSON template."
                                              "{'query': '<query here>', 'explanation': '<explanation here>'}."
                                              "You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            response_format={"type": "json_object"}
        )

        # Extract the response from the assistant
        try:
            jsn = json.loads(clean_markdown_response(response.choices[0].message.content))
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON response from OpenAI.")
        query = jsn["query"]
        explanation = jsn["explanation"]

        return query, explanation

    def get_schema(self) -> str:
        """
        Method that retrieves the schema from Neo4j using CALL apoc.meta.schema().
        """
        with graphdb.session() as session:
            schema_results = session.run("CALL apoc.meta.schema()")
            schema = schema_results.single()
            return json.dumps(schema, default=str)

    def execute_query(self, query: str) -> list:
        """
        Executes the given Neo4j query and returns the result as a dictionary.

        Args:
            query: The Neo4j query to execute.

        Returns:
            The result of the query.
        """
        logger.info(f"Executing query: {query}")
        try:
            with graphdb.session() as session:
                result = session.run(query)
                return [record.data() for record in result]
        except CypherSyntaxError as e:
            return [{"error": str(e)}]
        except CypherTypeError as e:
            return [{"error": str(e)}]

    def cast_query(self, query: Union[Dict,List]) -> str:
        """
        Casts the query result to a string.

        Args:
            query: The query result.

        Returns:
            The query result as a string.
        """
        return json.dumps(query, indent=2)
