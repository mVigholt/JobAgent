import chainlit as cl
from pydantic_ai import UsageLimits

from agents import job_agent
from error_handling import handle_agent_error
from settings import DEFAULT_LIST_SIZE, MAX_LIST_SIZE, MAX_SAVED_SEARCHES
from storage import (
    delete_saved_search,
    get_saved_search_by_number,
    get_saved_searches,
    save_search,
)


async def ask_optional(question: str) -> str:
    response = await cl.AskUserMessage(content=question, timeout=300).send()
    return response["output"].strip() if response else ""


def parse_list_size(value: str) -> int:
    if not value:
        return DEFAULT_LIST_SIZE

    try:
        number = int(value)
    except ValueError:
        return DEFAULT_LIST_SIZE

    return max(1, min(number, MAX_LIST_SIZE))


async def ask_search_radius() -> tuple[str, str]:
    choice = await ask_optional(
        "Hvordan vil du begrænse søgeområdet?\n\n"
        "1. Kilometer\n2. Transporttid i minutter\n3. Ingen begrænsning"
    )

    if choice == "1":
        return "km", await ask_optional("Maksimal afstand i kilometer:")
    if choice == "2":
        return "minutes", await ask_optional("Maksimal transporttid i minutter:")
    return "", ""


def format_search_radius(search: dict[str, str]) -> str:
    value = search.get("search_radius_value", "")
    radius_type = search.get("search_radius_type", "")

    if not value:
        return "Ingen begrænsning"
    if radius_type == "km":
        return f"{value} km"
    if radius_type == "minutes":
        return f"{value} min."
    return "Ingen begrænsning"


def format_saved_searches(searches: list[dict[str, str]]) -> str:
    if not searches:
        return "Du har ingen gemte søgninger."

    lines = ["## Gemte søgninger", ""]
    for number, search in enumerate(searches, start=1):
        lines.append(
            f"**{number}.** "
            f"{search.get('experience_education') or 'Ikke angivet'}"
            f" | {search.get('keywords') or 'Alle jobs'}"
            f" | {search.get('location') or 'Alle lokationer'}"
            f" | {format_search_radius(search)}"
            f" | {search.get('list_size') or DEFAULT_LIST_SIZE} jobs"
        )
        lines.append("")
    return "\n".join(lines)


async def create_new_search() -> None:
    if len(get_saved_searches()) >= MAX_SAVED_SEARCHES:
        await cl.Message(
            content=(
                f"Du har allerede {MAX_SAVED_SEARCHES} gemte søgninger. "
                "Slet en eksisterende søgning først."
            )
        ).send()
        return

    experience_education = await ask_optional("Erfaring / uddannelse:")
    location = await ask_optional("Lokation:")
    radius_type, radius_value = await ask_search_radius()
    keywords = await ask_optional("Keywords:")
    platforms = await ask_optional("Foretrukne platforme:")
    list_size = parse_list_size(
        await ask_optional(
            f"Hvor mange jobs vil du have vist? "
            f"(standard: {DEFAULT_LIST_SIZE}, maks: {MAX_LIST_SIZE})"
        )
    )

    search = {
        "experience_education": experience_education,
        "location": location,
        "search_radius_type": radius_type,
        "search_radius_value": radius_value,
        "keywords": keywords,
        "preferred_platforms": platforms,
        "list_size": str(list_size),
    }

    success, message = save_search(search)
    if not success:
        await cl.Message(content=message).send()
        return

    await cl.Message(
        content=(
            "✅ Søgningen er gemt.\n\n"
            f"**Erfaring / uddannelse:** {experience_education or 'Ikke angivet'}\n"
            f"**Lokation:** {location or 'Ikke angivet'}\n"
            f"**Radius:** {format_search_radius(search)}\n"
            f"**Keywords:** {keywords or 'Ikke angivet'}\n"
            f"**Platforme:** {platforms or 'Ikke angivet'}\n"
            f"**Antal jobs:** {list_size}"
        )
    ).send()


async def choose_saved_search() -> dict[str, str] | None:
    searches = get_saved_searches()
    if not searches:
        await cl.Message(content="Du har ingen gemte søgninger.").send()
        return None

    await cl.Message(content=format_saved_searches(searches)).send()
    response = await ask_optional("Indtast nummeret på den søgning, du vil bruge:")

    try:
        number = int(response)
    except ValueError:
        await cl.Message(content="Indtast venligst et gyldigt nummer.").send()
        return None

    search = get_saved_search_by_number(number)
    if search is None:
        await cl.Message(content="Den valgte søgning findes ikke.").send()
    return search


async def delete_saved_search_flow() -> None:
    searches = get_saved_searches()
    if not searches:
        await cl.Message(content="Du har ingen gemte søgninger.").send()
        return

    await cl.Message(content=format_saved_searches(searches)).send()
    response = await ask_optional("Indtast nummeret på den søgning, du vil slette:")

    try:
        number = int(response)
    except ValueError:
        await cl.Message(content="Indtast venligst et gyldigt nummer.").send()
        return

    _, message = delete_saved_search(number)
    await cl.Message(content=message).send()


async def run_job_search(search: dict[str, str]) -> None:
    prompt = f"""
Find aktuelle og relevante job ud fra denne søgeprofil:

Erfaring / uddannelse: {search.get('experience_education') or 'Ikke angivet'}
Lokation: {search.get('location') or 'Ikke angivet'}
Søgeradius: {format_search_radius(search)}
Keywords: {search.get('keywords') or 'Ikke angivet'}
Foretrukne platforme: {search.get('preferred_platforms') or 'Ingen præference'}
Maksimalt antal jobs: {search.get('list_size') or DEFAULT_LIST_SIZE}

Planlæg selv en bred, intelligent søgning. Kald det samlede søgeværktøj én gang,
og foretag derefter selv relevansvurderingen. Et job, der kun matcher lokationen,
men ikke profilen eller fagområdet, er ikke relevant og skal udelades.
"""

    status = cl.Message(content="🔎 Agenten planlægger jobsøgningen...")
    await status.send()

    try:
        result = await job_agent.run(
            prompt,
            deps=parse_list_size(search.get("list_size", "")),
            usage_limits=UsageLimits(
                request_limit=2,
                tool_calls_limit=1,
            ),
        )
        status.content = str(result.output)
    except Exception as error:
        # Finish the old status message before asking for a replacement key.
        # Otherwise Chainlit updates this earlier message above the key prompt,
        # which makes it look as if no response was sent after the user's input.
        status.content = "⚠️ Jobsøgningen blev afbrudt."
        await status.update()

        follow_up_message = await handle_agent_error(error)
        await cl.Message(content=follow_up_message).send()
        return

    await status.update()
