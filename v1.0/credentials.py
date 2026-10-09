import os

import chainlit as cl
from dotenv import load_dotenv, set_key

from settings import ENV_FILE


load_dotenv(dotenv_path=ENV_FILE)


def load_api_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "").strip()


async def request_api_key(message_text: str) -> str:
    """Ask for a key and persist it as GOOGLE_API_KEY in .env."""
    response = await cl.AskUserMessage(content=message_text, timeout=300).send()
    if not response:
        return ""

    api_key = response["output"].strip()
    if not api_key:
        return ""

    set_key(
        dotenv_path=str(ENV_FILE),
        key_to_set="GOOGLE_API_KEY",
        value_to_set=api_key,
        quote_mode="always",
    )
    os.environ["GOOGLE_API_KEY"] = api_key
    return api_key
