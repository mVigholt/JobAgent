from agents import configure_model
from credentials import request_api_key


async def handle_agent_error(error: Exception) -> str:
    """Create a user-facing error and handle replaceable API keys."""
    error_text = str(error)

    if "request_limit" in error_text or "tool_calls_limit" in error_text:
        return (
            "Agenten forsøgte at overskride den faste grænse på to "
            "Gemini-kald og ét søgetool-kald. Søgningen blev stoppet uden "
            "yderligere API-forbrug. Prøv søgningen igen."
        )

    if "429" in error_text or "quota" in error_text.lower():
        new_api_key = await request_api_key(
            "Google returnerede fejl 429. Det kan være grænsen for kald pr. "
            "minut, tokens pr. minut eller dagens kvote — det betyder derfor "
            "ikke nødvendigvis, at nøglen er opbrugt. Vent eventuelt et minut, "
            "eller indtast en anden Gemini API-nøgle for at erstatte den "
            "nuværende i `.env`. Lad feltet være tomt for at beholde den:"
        )

        if new_api_key:
            configure_model(new_api_key)
            return (
                "API-nøglen er erstattet i `.env`. "
                "Start venligst søgningen igen."
            )

        return (
            "Den eksisterende API-nøgle blev beholdt.\n\n"
            f"{type(error).__name__}: {error}"
        )

    if (
        "API key not valid" in error_text
        or "401" in error_text
        or "UNAUTHENTICATED" in error_text
    ):
        new_api_key = await request_api_key(
            "API-nøglen blev afvist. Indtast en ny Google Gemini "
            "API-nøgle. Den nye nøgle erstatter den gamle i `.env`:"
        )

        if new_api_key:
            configure_model(new_api_key)
            return (
                "Nøglen er opdateret i `.env`. "
                "Start venligst søgningen igen."
            )

        return "Ingen ny API-nøgle blev angivet."

    return f"Systemfejl: {type(error).__name__}: {error}"
