import json
import logging
import warnings

from ha import config
from ha.agent.executor import QueryExecutor
from ha.agent.planner import Planner
from ha.tools.plan import PlanExecutor
from ha.models import openai_client as client
from ha.utils import green, blue, print_pretty_tasks

# Set up logging
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class HypothesisAgent:
    def __init__(self, model: str = config.OPENAI_AGENT_MODEL):
        """
        Initializes the ha core.

        Args:
            model: The model to use for the user interactions.
        """
        self.conversation_history = [
            {"role": "system", "content": "You are a system that generates responses to user input."}
        ]
        self.model = model
        self.planner = Planner(model=model)
        self.plan_executor = PlanExecutor(model=model)
        self.query_executor = QueryExecutor(model=model)

    @staticmethod
    def ha_says(message: str):
        """
        Print a message from the HA.

        Args:
            message: The message to print.
        """
        print(blue('\n\nha: ') + message)

    @staticmethod
    def user_says():
        """
        Prints the user input prompt and gets the user input.

        Returns:
            The user input.
        """
        return input(green("\nyou: "))

    def start(self):
        """
        Starts the user interaction in the command line.
        """
        self.ha_says(
              f"Hello! My name is {blue('ha')}, and I am an experimental agent specialising in biomedical research. "
              f"I have access to KEGG and GAF data. You can ask me anything related to these topics. "
              f"And other things. Type 'clear' to reset the conversation. Type 'exit' to quit or press ctrl+c."
        )

        while True:
            try:
                user_input = self.user_says()
                print('')
            except KeyboardInterrupt:
                self.ha_says("Bye!")
                break

            if user_input.lower() == 'exit':
                self.ha_says("Bye!")
                break
            elif user_input.lower() == 'clear':
                self.conversation_history = []
                self.ha_says("Conversation history cleared.")
                continue

            agent_reply = self.handle_user_input(user_input)
            self.ha_says(agent_reply)

    def set_objective(self, conversation: list) -> str:
        """
        Set the objective for the conversation.

        Args:
            conversation: The conversation history.

        Returns:
            The objective for the conversation.
        """
        prompt = (f"We are about to give a task to a biomedical hypothesis agent with access to KEGG and GAF data."
                  f"Given the following conversation history, set the objective for the agent. "
                  f"Be very brief and specific."
                  f"Conversation History:\n{json.dumps(conversation)}\n")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that sets objectives based on conversation history."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def handle_user_input(self, user_input: str):
        """
        Choose an action based on the conversation history. Possible actions are:
        1. Answer directly -- choose this if the question is not related to KEGG or GAF data.
        2. Ask a follow-up question -- choose if you think you need more information; max 3 follow-ups.
        3. Pass to the HA -- choose if the question is related to KEGG or GAF data and analysis.

        Args:
            user_input: The user input.

        Returns:
            The action chosen by the chatbot.
        """
        prompt = (f"Given the following conversation history, choose the best action to take next."
                  f"Conversation History:\n{json.dumps(self.conversation_history)}\n"
                  f"And user input: {user_input}\n\n"
                  f"Choose the best action to take next, focus on the later part of the conversation:\n"
                  f"1. answer -- choose this if the question is NOT in the biomedical domain, related to genes, "
                  f"KEGG or GAF data.\n"
                  f"2. ask -- ask a follow-up question; choose if you think you need more information; max 3 follow-ups.\n"
                  f"3. agent -- choose if the question is related to biomedical domain, KEGG or GAF data and analysis.\n"
                  f"Respond with the following JSON: {{'action': '<action here: answer/ask/agent>'}}")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that makes decisions and responds with JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        try:
            jsn = json.loads(response.choices[0].message.content)
            action = jsn["action"]
            logger.info(f"Action chosen: {action}")
            match action:
                case "answer":
                    return self.get_response(user_input)
                case "ask":
                    return self.ask_follow_up(user_input)
                case "agent":
                    return self.ask_ha(user_input)
                case _:
                    return self.handle_user_input(user_input)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from {self.model}. Response: {response}")
            return self.handle_user_input(user_input)
        except KeyError:
            logger.error(f"KeyError: 'action' not found in response. Response: {response}")
            return self.handle_user_input(user_input)

    def get_response(self, user_input):
        """
        Get the response from the OpenAI API based on user input.

        Args:
            user_input: The user input.

        Returns:
            The response from the chatbot.
        """
        # Add the user input to the conversation history
        self.conversation_history.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(model=self.model, messages=self.conversation_history)
            bot_reply = response.choices[0].message.content

            # Add the bot reply to the conversation history
            self.conversation_history.append({"role": "assistant", "content": bot_reply})

            return bot_reply
        except Exception as e:
            return f"Error: {e}"

    def ask_follow_up(self, user_input: str):
        """
        Ask a follow-up question based on the user input.

        Args:
            user_input: The user input.

        Returns:
            The follow-up question generated by the chatbot.
        """
        prompt = f"Given the user input: {user_input}, generate a follow-up question to get more information."
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates follow-up questions."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def ask_ha(self, user_input: str):
        """
        Pass the user input to the HA for analysis.

        Args:
            user_input: The user input.

        Returns:
            The response from the HA.
        """
        self.ha_says("Hey, I think I need to do a bit of analysis on this. It will take a while...\n")
        conversation = [f'{i["role"]}: {i["content"]}'
                        for i in self.conversation_history + [{"role": "user", "content": user_input}]]
        objective = self.set_objective(conversation)
        plan = self.planner.run(
            conversation=conversation,
            objective=objective,
        )
        self.ha_says(f"I have a plan. Here's a peek:\n")
        print_pretty_tasks(plan)
        self.ha_says("\n\nExecuting the plan...\n")
        analysis = self.plan_executor.run(plan)
        self.ha_says(f"Analysis complete.")
        hypothesis = self.generate_hypothesis(
            analysis=json.dumps(analysis),
            conversation=json.dumps(conversation),
            objective=objective
        )
        return hypothesis

    def generate_hypothesis(self, analysis: str, conversation: str, objective: str) -> str:
        """
        Generate a hypothesis based on the analysis.

        Args:
            analysis: The analysis results.
            conversation: The conversation history.
            objective: The objective for the conversation.

        Returns:
            The hypothesis generated by the chatbot.
        """
        prompt = (f"Given the following analysis results: {analysis}\n"
                  f"And the original conversation and analysis objective:\n"
                  f"Conversation: {conversation}\n"
                  f"Objective: {objective}\n"
                  f"Generate an appropriate hypothesis. Include any relevant information from the analysis, "
                  f"especially names of genes, any counts, values and other useful data.")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates hypotheses based on analysis results."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content