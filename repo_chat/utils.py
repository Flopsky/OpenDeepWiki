import google.generativeai as genai
from openai import OpenAI
from google.generativeai import caching
import dotenv
import os
import threading
from anthropic import Anthropic, Timeout
import logging
import traceback
logger = logging.getLogger(__name__)


# Thread-local storage for model clients
thread_local = threading.local()

dotenv.load_dotenv()

#TODO  MOVE the model init in a separated file.

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
try:
    if OPENAI_API_KEY and OPENAI_API_KEY != "...":
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
except Exception as e:
    client = None
    logger.info("OpenAI client not initialized, the api key is not set, the value is %s", OPENAI_API_KEY)



try:
    if GEMINI_API_KEY and GEMINI_API_KEY != "...":
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialized")
except Exception as e:
    genai = None
    logger.info("Gemini client not initialized, the api key is not set, the value is %s", GEMINI_API_KEY)

# Define safety settings
safe = [
    {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Initialize the clients
client_8b = genai.GenerativeModel(
    model_name="gemini-1.5-flash-8b-001",
    safety_settings=safe,
    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 8000},
)

client_exp_flash = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    safety_settings=safe,
    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 8000},
)

client_exp_pro = genai.GenerativeModel(
    model_name="gemini-exp-1206",
    safety_settings=safe,
    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 8000},
)

client_flash = genai.GenerativeModel(
    model_name="gemini-1.5-flash-002",
    safety_settings=safe,
    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 8000},
)

client_pro = genai.GenerativeModel(
    model_name="gemini-1.5-pro-002",
    safety_settings=safe,
    generation_config={"temperature": 0, "top_p": 1, "max_output_tokens": 8000},
)





client_25pro_preview = genai.GenerativeModel(
    model_name="gemini-2.5-pro-preview-03-25",
    safety_settings=safe,
    generation_config={"temperature": 0.95, "top_p": 1, "max_output_tokens": 60000},
)

def get_gemini_pro_25_response(prompt: str) -> str:
    response = client_25pro_preview.generate_content(prompt)
    return response


def get_openai_gpt4_1_response(system_prompt: str = None, user_prompt: str = None) -> str:
    response = client.chat.completions.create(
        model="gpt-4.1-2025-04-14",
        messages=[{"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}] if system_prompt else [{"role": "user", "content": user_prompt}],
    )
    return response#.choices[0].message.content

def get_openai_o4_mini_response(user_prompt: str = None) -> str:
    response = client.responses.create(
        model="o3",
        reasoning={"effort": "high"},
    input=[
        {"role": "user", "content": user_prompt}
        ]
    )
    return response.output_text

def get_claude_response(system_prompt: str = None, user_prompt: str = None) -> str:
    """
    Get response from Claude 3.7 Sonnet with extended timeout
    Args:
        prompt: User's input text
    Returns:
        Claude's response as text
    """
    client = Anthropic(
        timeout=Timeout(
            60.0 * 30,  # 30 minutes timeout
            connect=5.0,
        ),
        api_key=ANTHROPIC_API_KEY,
    )

    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=64000,
        thinking={
            "type": "enabled",
            "budget_tokens": 32000,  # Maximum recommended thinking budget
        },
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
            ] 
    )

    return response.content[1].text if not system_prompt else response


SAFE = [
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
