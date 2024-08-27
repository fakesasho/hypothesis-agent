import json
import logging
from typing import Tuple

from ha.models import openai_client as client
from ha import config
from ha.utils import generative_execution, clean_markdown_response

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


tips = """
- use the tool description to imagine what type of instructions a lower level agent might need.
- use any specific details about the tool to inform the questions you ask and goals you set.
- use the objective and expand it in the context of the tool and its capabilities.
"""


class Instructor:

    NAME = "Instructor"

    def __init__(self, model: str = config.OPENAI_AGENT_MODEL):
        self.model = model
        self.attempts = 3
        self.default_attempts = 3
        self.action_log = []

    def run(self, objective: str, tool: str, schema: str, reflection: str = '') -> dict:
        """
        Runs the instructor. This is the main method that should be called to run the instructor.

        Args:
            objective: Objective based on the plan
            tool: The tool based on the plan
            schema: The schema for the query
            reflection: The user's reflection on the previous response

        Returns:
            The detailed instructions for the agent.
        """
        self.attempts = self.default_attempts
        return self._run(objective, tool, schema, reflection)

    def _run(self, objective: str, tool: str, schema: str, reflection: str = '') -> dict:
        """
        Runs the instructor. This is hidden in order to keep the attempts counter intact.

        Args:
            objective: Objective based on the plan
            tool: The tool based on the plan
            schema: The schema for the query
            reflection: The user's reflection on the previous response

        Returns:
            The detailed instructions for the agent.
        """
        instructions = self.generate_instructions(objective, tool, schema, reflection)
        instructions_str = json.dumps(instructions) # Convert the instructions back to string; not great
        reflection_success, reflection = self.reflect(objective, tool, instructions_str)
        self.attempts -= 1
        self.log(objective, tool, instructions, reflection_success, reflection)
        if reflection_success:
            logger.info(f"{self.NAME} thinks their answer is correct.")
            return instructions
        elif self.attempts:
            logger.info(f"{self.NAME} thinks their answer is incorrect because: {reflection}. Retrying... Attempts left: {self.attempts}")
            return self._run(objective, tool, reflection)
        else:
            logger.error(f"{self.NAME} failed after {self.default_attempts} attempts. Passing the log.")
            return ({
                "error": f"Reflection failed after {self.default_attempts} attempts.",
                "log": self.action_log
            })


    @generative_execution
    def generate_instructions(self, objective: str, tool: str, schema: str, reflection: str = 'not available') -> dict:
        """
        Generates detailed instructions for the agent based on the short instructions.

        Args:
            objective: The objective based on the plan
            tool: The tool based on the plan
            schema: The schema for the query
            reflection: The user's reflection on the previous response

        Returns:
            The detailed instructions for the agent.
        """
        prompt = (
            f"Generate a detailed instruction for completing the objective using the designated tool.\n"
            f"Remember that this should be done in only ONE step using the tool.\n"
            f"Include a JSON goal template for the output data structure that would satisfy the request. "
            f"Use the provided schema to identify what information types are important or can be derived from the"
            f"tool data source.\n"
            f"If none is required use 'flexible' to leave it to the executor.\n"
            f"Objective: {objective}\n"
            f"Tool: {tool}\n"
            f"Relevant Schema: {schema}\n\n"
            f"Use this reflection if available <<{reflection}>>\n"
            f"And these tips: {tips}\n"
        )

        # Send the image and text prompt to GPT-4 with Vision
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates instructions using a JSON template."
                                              "{'instructions': '<instructions here>', "
                                              "'goal_template': '<explanation here>'}."
                                              "You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            response_format={"type": "json_object"}
        )

        # Extract the response from the assistant and parse as JSON; important to validate the output at this point
        try:
            return json.loads(clean_markdown_response(response.choices[0].message.content))
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            raise ValueError(f"Failed to decode JSON response from {self.model}. Response: {response}")

    @generative_execution
    def reflect(self, objective: str, tool: str, instructions: str) -> Tuple[bool, str]:
        """
        Reflects on the generated instructions and determines if they are appropriate and satisfactory. If so,
        the method should return True and a reflection message. If not, the method should return False and
        a reflection message.

        Args:
            objective: The instructions for the query.
            tool: The goal template for the query.
            instructions: The response from the query.

        Returns:
            A tuple containing a boolean indicating if the instructions are appropriate and a reflection message.
        """
        logger.info(f"Reflecting on the instructions.")
        prompt = (f"Consider the following objective: <<{objective}>>\n"
                  f"And the tool that is supposed to be used to complete it: <<{tool}>>\n--\n"
                  f"Now determine if the following detailed instructions and "
                  f"output data template are appropriate:\n{instructions}\n--\n"
                  f"You should reflect and decide whether:\n"
                  f"1. The instructions will lead to an appropriate answer to the objective.\n"
                  f"2. The instructions can realistically be followed using the specified tool.\n"
                  f"3. Determine if the data goal template is appropriate WRT the objective.")
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

    def log(self, objective: str, tool: str, instructions: dict, reflection_success: bool, reflection: str):
        """
        Logs the action taken by the instructor.

        Args:
            objective: The objective based on the plan.
            tool: The tool based on the plan.
            instructions: The detailed instructions for the agent.
            reflection_success: Whether the reflection was successful.
            reflection: The reflection on the query response.
        """
        self.action_log.append(
            {
                "objective": objective,
                "tool": tool,
                "instructions": instructions,
                "reflection_success": reflection_success,
                "reflection": reflection,
                "attempt": self.default_attempts - self.attempts,
            }
        )