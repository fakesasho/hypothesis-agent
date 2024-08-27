import re


def generative_execution(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                return {"error": str(e)}
    return wrapper


def clean_markdown_response(text: str) -> str:
    """
    Clean the markdown response from OpenAI.

    Args:
        text: The markdown response from OpenAI.

    Returns:
        The cleaned markdown response.
    """
    # handle no text
    if text is None:
        return None
    elif type(text) is not str:
        return text

    # Remove markdown
    text = re.sub(r'```[a-z0-9]*', '', text)
    return text


def green(text: str) -> str:
    """
    Returns the given text string wrapped in ANSI escape codes to make it green.
    """
    return f"\033[92m{text}\033[0m"


def blue(text: str) -> str:
    """
    Returns the given text string wrapped in ANSI escape codes to make it blue.
    """
    return f"\033[94m{text}\033[0m"


def print_pretty_tasks(tasks):
    # ANSI escape codes for colors
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

    for i, task in enumerate(tasks, 1):
        print(f"{CYAN}Task {i}:{RESET}")
        print(f"  {YELLOW}Objective:{RESET} {task['objective']}")
        print(f"  {GREEN}Tool:{RESET} {task['tool']}")
        print(f"{MAGENTA}{'-' * 40}{RESET}")
