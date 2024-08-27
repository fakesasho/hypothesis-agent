import logging
import json
from typing import Union, Dict, List, Tuple, Any

from ha.utils import generative_execution
from ha.models import openai_client as client
from ha.utils import clean_markdown_response

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QueryExecutor:
    NAME = "Query Executor"
    def __init__(self, model: str, attempts: int = 3):
        """
        Initializes the query executor.

        Args:
            model: The model to use for the query.
            attempts: The number of attempts to try the query before failing.
        """
        self.model = model
        self.attempts = attempts
        self.default_attempts = attempts
        self.action_log = []

    def run(self, instructions: str, goal_template: str = 'flexible', reflection: str = '') -> Any:
        """
        Runs the query executor. This is the main method that should be called to run the query executor.

        Args:
            instructions: The user's instruction/inquiry.
            goal_template: The goal template for the query.
            reflection: The user's reflection on the previous response

        Returns:
            The result of the query
        """
        self.attempts = self.default_attempts
        return self._run(instructions, goal_template, reflection)

    def _run(self, instructions: str, goal_template: str = 'flexible', reflection: str = '') -> Any:
        """
        Runs the query executor. This is hidden in order to keep the attempts counter intact.

        Args:
            instructions: The user's instruction/inquiry.
            goal_template: The goal template for the query.
            reflection: The user's reflection on the previous response

        Returns:
            The result of the query
        """
        query, explanation = self.generate_query(instructions, goal_template, reflection, self.get_schema())
        query_response = self.execute_query(query)
        query_response_str = self.cast_query(query_response)
        reflection_success, reflection = self.reflect(
            instructions=instructions,
            goal_template=goal_template,
            query=query,
            explanation=explanation,
            response=query_response_str)
        self.attempts -= 1
        self.log(instructions, goal_template, query_response_str, reflection_success, reflection)
        if reflection_success:
            logger.info(f"{self.NAME} thinks their answer is correct.")
            return self.generate_response(instructions, goal_template, reflection, query_response_str)
        elif self.attempts:
            logger.info(f"{self.NAME} thinks their answer is incorrect because:{reflection}. Retrying... Attempts left: {self.attempts}")
            return self._run(instructions, goal_template, reflection)
        else:
            logger.error(f"{self.NAME} failed after {self.default_attempts} attempts. Passing the log.")
            return ({
                "error": f"Reflection failed after {self.default_attempts} attempts.",
                "log": self.action_log
            })

    @generative_execution
    def generate_query(self, instructions: str, goal_template: str, reflection: str, schema: str) -> tuple:
        """
        Generates a query based on the instructions, goal template, reflection, and schema.

        Args:
            instructions: The instructions for the query.
            goal_template: The goal template for the query.
            reflection: The reflection on the query response.
            schema: The schema of the data.

        Returns:
            The generated query string.
        """
        pass

    def execute_query(self, query: str) -> Union[Dict,List]:
        """
        Executes the query and returns the result.

        Args:
            query: The query string.

        Returns:
            The result of the query, typically a dictionary or a list.
        """
        pass

    @generative_execution
    def reflect(self, instructions: str, goal_template: str, query: str, response: str,
                explanation: str) -> Tuple[bool, str]:
        """
        Reflects on the query response and determines if the response is correct or satisfactory. If the response is
        correct, the method should return True and a reflection message. If the response is incorrect, the method should
        return False and a reflection message.

        Args:
            instructions: The instructions for the query.
            goal_template: The goal template for the query.
            query: The query that was executed.
            response: The response from the query.
            explanation: The explanation for the query.

        Returns:
            A tuple containing a boolean indicating if the response is correct and a reflection message.
        """
        logger.info(f"Reflecting on the query response.")
        prompt = (f"Consider the following query: <<{query}>>\n"
                  f"And its explanation: <<{explanation}>>\n--\n"
                  f"And its results:\n{response}\n--\n"
                  f"They were generated based on the initial instructions: <<{instructions}>>\n"
                  f"You should reflect and decide whether:\n"
                  f"1. The query is appropriate to address the instructions\n"
                  f"2. The results can be used to generate a satisfactory response. "
                  f"Bear in mind sometimes no results are also acceptable.\n"
                  f"3. When deciding if the results are appropriate bear in mind "
                  f"the original goal data template if specified. See here:\n{goal_template}")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates judgements using a JSON template."
                                              "Your response should follow this format:\n"
                                              "{'acceptance': true/false, 'reflection': '<reflection here>'}"
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
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            raise ValueError(f"Failed to decode JSON response from {self.model}. Response: {response}")
        acceptance = jsn["acceptance"]
        reflection = jsn["reflection"]

        return acceptance, reflection

    def generate_response(self, instructions: str, goal_template: str, reflection: str, query_response: str) -> str:
        """
        Generate a response based on the instructions, goal template, reflection, and query response.

        Args:
            instructions: The instructions for the query.
            goal_template: The goal template for the query.
            reflection: The reflection on the query response.
            query_response: The query response.

        Returns:
            The response to the query.
        """
        prompt = (f"Given the following instructions: {instructions}\n"
                  f"Reflecting on the query response: {reflection}\n"
                  f"And the goal data template: {goal_template}\n"
                  f"Generate a response based on the query results: {query_response}")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates responses to instructions."
                                              "If provided your response should follow a specified data format"},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ]
        )

        return response.choices[0].message.content

    def get_schema(self) -> str:
        """
        Get the schema of the database that is being queried.

        Returns:
            The schema of the database as a string.
        """
        pass

    def cast_query(self, query: Union[Dict,List, str]) -> str:
        """
        Casts the query response to a string.

        Args:
            query: The query response.

        Returns:
            The query response as a string.
        """
        return query

    def log(self, instructions: str, goal_template: str, generated_response: str,
            reflection_success: bool, reflection: str):
        """
        Adds the current query and parameters to the action log.

        Args:
            instructions: The instructions for the query.
            goal_template: The goal template for the query.
            generated_response: The response generated by the query.
            reflection_success: Whether the reflection was successful.
            reflection: The reflection on the query response.
        """
        self.action_log.append(
            {
                "instructions": instructions,
                "goal_template": goal_template,
                "response": generated_response,
                "reflection_success": reflection_success,
                "reflection": reflection,
                "attempt": self.default_attempts - self.attempts,
            }
        )