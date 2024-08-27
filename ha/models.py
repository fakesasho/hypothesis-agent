import logging

import openai
from ha import config


# Get the OpenAI logger
openai_logger = logging.getLogger("openai")

# Set the logging level to CRITICAL (or you can use a higher level like logging.FATAL)
openai_logger.setLevel(logging.CRITICAL)

# Suppress logs from the 'requests' library
requests_logger = logging.getLogger("requests")
requests_logger.setLevel(logging.CRITICAL)  # or higher level like logging.FATAL

# Suppress logs from 'urllib3' (which 'requests' uses)
urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.CRITICAL)

# Set the OpenAI API key
openai.api_key = config.OPENAI_API_KEY
openai_client = openai.Client()
