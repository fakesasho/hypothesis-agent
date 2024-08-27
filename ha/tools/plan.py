import json
import logging
from typing import Any, Dict, List

from ha import config
from ha.models import openai_client as client
from ha.tools.instructor import Instructor
from ha.tools.kegg import Kegg
from ha.tools.gaf import Gaf
from ha.tools.graph import GraphAnalysis
from ha.utils import generative_execution, clean_markdown_response


# set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PlanExecutor:

    NAME = "Plan Executor"

    tool_registry = {
        "kegg_query": Kegg(),
        "gaf_query": Gaf(),
        "graph_analysis": GraphAnalysis()
    }

    def __init__(self, model: str = config.OPENAI_AGENT_MODEL):
        self.todo: list = []
        self.focus: Any = None
        self.done: list = []
        self.instructor = Instructor()
        self.model = model

    def run(self, plan: List[Dict]) -> List[Dict]:
        """
        Runs the plan executor. This is the main method that should be called to run the plan executor.

        The plan is a list of dictionaries. Each item in the plan should have an objective and a tool name.

        Args:
            plan: The plan to execute.

        Returns:
            The result of the plan execution.
        """
        self._reset()
        self.todo = plan.copy()
        counter = 0
        while self.todo:
            self.focus = self.todo.pop(0)
            tool = self.tool_registry[self.focus["tool"]]
            instructions_obj = self.instructor.run(
                objective=self.focus["objective"],
                tool=self.focus["tool"],
                schema=tool.get_schema()
            )
            completed = tool.run(instructions_obj["instructions"], instructions_obj["goal_template"])
            acceptance, feedback = self.reflect(completed)
            if not acceptance:
                # TODO: add a planner to re-plan the item here
                pass
            counter += 1
            logger.info(f"Item completed: {counter}")
            self.done.append(
                {
                    "objective": self.focus["objective"],
                    "tool": self.focus["tool"],
                    "instructions": instructions_obj,
                    "feedback": feedback,
                    "response": completed
                }
            )
        return self.done

    def execute_item(self, instructions_text: str, tool_name: str, goal_template: str) -> str:
        """
        Executes a single item in the plan using a tool and based on the instructions.

        Args:
            instructions_text: The user's instruction/inquiry.
            tool_name: The name of the tool to use.
            goal_template: The goal template for the query.

        Returns:
            The result of the item execution.
        """
        tool = self.tool_registry[tool_name]
        return tool.run(instructions_text, goal_template)

    @generative_execution
    def reflect(self, completed: str) -> tuple:
        """
        Reflects on the execution of the plan after each item is completed.

        Args:
            completed: The result of the latest completed item.

        Returns:
            A tuple with the acceptance of the reflection and the feedback.
        """
        logger.info(f"Reflecting on the execution.")
        prompt = (
            f"Reflect on the following plan that is being executed:\n"
            f"-Past executed items with their results:\n{json.dumps(self.done)}\n\n"
            f"-Latest item executed:\n{completed}\n\n"
            f"-Remaining items to execute:\n{json.dumps(self.todo)}\n\n"
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

    def _reset(self):
        """
        Resets the plan executor.
        """
        self.todo = []
        self.focus = None
        self.done = []
