import chainlit as cl

from agents import configure_model, job_agent
from credentials import load_api_key, request_api_key
from settings import MODEL_NAME
from storage import get_saved_searches, initialise_files
from workflows import (
    choose_saved_search,
    create_new_search,
    delete_saved_search_flow,
    format_saved_searches,
    run_job_search,
)

@cl.on_chat_start
async def start() -> None:
    initialise_files()
    api_key = load_api_key()

    if not api_key:
        api_key = await request_api_key(
            "Velkommen! Jeg kunne ikke finde `GOOGLE_API_KEY` i miljøet. "
            "Indtast din Google Gemini API-nøgle. Nøglen gemmes i projektets "
            "`.env`-fil:"
        )

    if not api_key:
        await cl.Message(content="Ingen API-nøgle blev angivet.").send()
        return

    configure_model(api_key)
    await cl.Message(
        content=(
            f"✅ **JobAgent er klar med {MODEL_NAME}!**\n\n"
            "Du kan f.eks. skrive:\n"
            "- `ny søgning`\n"
            "- `gemte søgninger`\n"
            "- `gentag søgning`\n"
            "- `slet søgning`"
        )
    ).send()


@cl.on_message
async def main(message: cl.Message) -> None:
    if job_agent.model is None:
        await cl.Message(
            content="Fejl: Ingen API-nøgle indstillet. Genstart venligst appen."
        ).send()
        return

    command = message.content.strip().lower()

    if command == "ny søgning":
        await create_new_search()
        return

    if command == "gemte søgninger":
        await cl.Message(content=format_saved_searches(get_saved_searches())).send()
        return

    if command == "gentag søgning":
        search = await choose_saved_search()
        if search is not None:
            await run_job_search(search)
        return

    if command == "slet søgning":
        await delete_saved_search_flow()
        return

    await cl.Message(
        content=(
            "❌ Det er ikke en gyldig kommando.\n\n"
            "Benyt en af følgende kommandoer:\n"
            "- `ny søgning`\n"
            "- `gemte søgninger`\n"
            "- `gentag søgning`\n"
            "- `slet søgning`"
        )
    ).send()
