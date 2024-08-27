import json
import logging
from typing import List

from ha import config
from ha.models import openai_client as client
from ha.utils import clean_markdown_response, generative_execution

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Planner:

    NAME = "Planner"

    def __init__(self, model: str = config.OPENAI_AGENT_MODEL, attempts: int = 3):
        """
        Initializes the planner.

        Args:
            model: The model to use for the planner.
            attempts: The number of attempts to try the planner before failing.
        """
        self.model = model
        self.attempts = attempts
        self.default_attempts = attempts
        self.action_log = []

    def run(self, conversation: List[str], objective: str, reflection: str = '') -> List[dict]:
        """
        Runs the planner. This is the main method that should be called to run the planner.

        Args:
            conversation: The conversation to plan.
            objective: Objective based on the plan
            reflection: The user's reflection on the previous response

        Returns:
            The plan for best proceeding with the conversation.
        """
        self.attempts = self.default_attempts
        return self._run(conversation, objective, reflection)

    def _run(self, conversation: List[str], objective: str, reflection: str = '') -> List[dict]:
        """
        Runs the planner. This is hidden in order to keep the attempts counter intact.

        Args:
            conversation: The conversation to plan.
            objective: Objective based on the plan
            reflection: The user's reflection on the previous response

        Returns:
            The plan for best proceeding with the conversation.
        """
        plan = self.generate_plan(
            conversation=json.dumps(conversation),
            objective=objective
        )
        acceptance, reflection = self.reflect(
            plan=json.dumps(plan),
            conversation=json.dumps(conversation),
            objective=objective,
            reflection=reflection
        )
        self.attempts -= 1
        self.log(
            plan=json.dumps(plan),
            conversation=json.dumps(conversation),
            objective=objective,
            reflection_success=acceptance,
            reflection=reflection
        )
        if acceptance:
            return plan
        elif self.attempts:
            return self._run(conversation, objective, reflection)
        else:
            return []

    @generative_execution
    def generate_plan(self, conversation: str, objective: str) -> List[dict]:
        """
        Generates a plan for the conversation based on the objective.

        Args:
            conversation: The conversation to plan.
            objective: Objective based on the plan

        Returns:
            The plan for best proceeding with the conversation.
        """
        logger.info(f"Generating a plan for the conversation with the objective: {objective}")
        prompt = (
            f"Given the following conversation:\n{conversation}\n"
            f"Generate a plan (a JSON list) that satisfies this high-level goal: {objective}\n"
            f"The plan should have at least one step and each step should have an objective and a designated tool."
            f"Make sure that the plan has steps that identify the corresponding entities within each dataset."
            f"For example, find the exact name of the colon cancer pathway in the KEGG database."
            f"Here's a list of the tools that can be used for the plan: \n{json.dumps(config.TOOL_DESCRIPTIONS)}\n\n"
            f"Here's a template that needs to be used for the plan: \n"
            f"{{ \"plan\": "
            f"[{{\"objective\": \"<lower level objective here>\", \"tool\": \"<best tool for the job here>\"}}}}]"
        )
        # Send the text prompt to GPT-4
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates plans using JSON template."
                                              "The response should be a list. Each item in the list look like this: \n"
                                              "{'objective': '<lower level objective here>', "
                                              "'tool': '<best tool for the job here>'}."
                                              "You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        # Parse the plan
        try:
            jsn = json.loads(clean_markdown_response(response.choices[0].message.content))
            if isinstance(jsn, dict):
                return jsn['plan']
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            raise ValueError(f"Failed to decode JSON response from {self.model}. Response: {response}")
        return jsn

    def reflect(self, plan: str, conversation: str, objective: str, reflection: str) -> tuple:
        """
        Reflects on the plan and generates a reflection.

        Args:
            plan: The plan to reflect on.
            conversation: The conversation to plan.
            objective: Objective based on the plan
            reflection: The user's reflection on the previous response

        Returns:
            A tuple containing a boolean indicating if the plan is appropriate and a reflection message.
        """
        logger.info(f"Reflecting on the plan.")
        prompt = (
            f"Consider the following plan: {plan}\n"
            f"Based on the conversation: {conversation}\n"
            f"And the high-level goal: {objective}\n"
            f"Reflect on the plan and decide whether it is appropriate and satisfactory.\n"
            f"Use this reflection if available: {reflection}\n"
        )
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

    def post_process(self, plan: dict):
        """
        Post-processes the plan by adding a reflection key to each item in the plan.

        Args:
            plan: The plan to post-process.
        """
        prompt = f"""
        Transform this JSON so that it looks like this. If you cannot find the right information respond with 'NO'.
        DO NOT RETURN A DICTIONARY. RETURN A LIST OF DICTIONARIES.
        {plan}
        TEMPLATE:
        [
            {{
                "objective": "<lower level objective here>",
                "tool": "<best tool for the job here>"
            }}
        ] 
        """
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system helps clean up JSON data. You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            # response_format={"type": "json_object"} # this is such a controversial feature
        )
        try:
            print('postprocessing ' + response.choices[0].message.content)
            if response.choices[0].message.content.lower() == "no":
                return
            return json.loads(clean_markdown_response(response.choices[0].message.content))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            raise ValueError(f"Failed to decode JSON response from {self.model}. Response: {response}")

    def log(self, plan: str, conversation: str, objective: str, reflection_success: bool, reflection: str):
        """
        Logs the action taken by the planner.

        Args:
            plan: The plan to log.
            conversation: The conversation to plan.
            objective: Objective based on the plan
            reflection_success: Whether the reflection was successful.
            reflection: The reflection on the query response.
        """
        self.action_log.append(
            {
                "plan": plan,
                "conversation": conversation,
                "objective": objective,
                "reflection_success": reflection_success,
                "reflection": reflection,
            }
        )
