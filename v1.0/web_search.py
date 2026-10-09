import asyncio
from datetime import date

from ddgs import DDGS

from settings import MAX_WEB_RESULTS


def _run_search(
    query: str,
    max_results: int,
    timelimit: str | None,
    backend: str,
) -> list[dict]:
    arguments = {
        "region": "dk-da",
        "safesearch": "moderate",
        "backend": backend,
        "max_results": max_results,
    }

    if timelimit is not None:
        arguments["timelimit"] = timelimit

    return DDGS(timeout=15).text(query, **arguments)


def _search_sync(query: str, max_results: int) -> list[dict[str, str]]:
    current_year = date.today().year
    attempts = [
        (query, "m", "duckduckgo"),
        (f"{query} {current_year}", None, "duckduckgo"),
        (query, None, "auto"),
    ]

    for attempt_query, timelimit, backend in attempts:
        try:
            results = _run_search(
                attempt_query,
                max_results,
                timelimit,
                backend,
            )
        except Exception:
            continue

        if not results:
            continue

        unique_results = []
        seen_urls = set()

        for result in results:
            url = result.get("href", "")
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            unique_results.append(
                {
                    "title": result.get("title", ""),
                    "url": url,
                    "description": result.get("body", ""),
                }
            )

        if unique_results:
            return unique_results

    return []


async def search_web(
    query: str,
    max_results: int = 10,
) -> list[dict[str, str]]:
    """Run the blocking DDGS client without blocking Chainlit."""
    bounded_limit = max(1, min(max_results, MAX_WEB_RESULTS))
    return await asyncio.to_thread(_search_sync, query, bounded_limit)
