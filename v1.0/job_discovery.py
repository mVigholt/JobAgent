import asyncio
import math
from itertools import zip_longest
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import storage
from page_inspection import (
    extract_job_links_from_listing,
    inspect_job_page,
    looks_like_listing_url,
)
from settings import (
    CANDIDATE_MULTIPLIER,
    MAX_INSPECTION_CANDIDATES,
    MAX_LIST_SIZE,
    MAX_LISTING_PAGES_PER_QUERY,
    MAX_VERIFIED_CANDIDATES,
    MAX_WEB_RESULTS,
    MIN_INSPECTION_CANDIDATES,
)
from web_search import search_web


def _normalise_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in {"trackingid", "trk", "ref"}
        ]
        return urlunsplit(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                parts.path.rstrip("/"),
                urlencode(query),
                "",
            )
        )
    except ValueError:
        return url.strip()


def _history_urls() -> set[str]:
    rows = storage.get_submitted_jobs() + storage.get_excluded_jobs()
    return {_normalise_url(row.get("url", "")) for row in rows if row.get("url")}


async def find_verified_jobs(
    queries: list[str],
    desired_jobs: int,
) -> list[dict[str, str]]:
    """Execute one agent-planned search batch and verify its candidates."""
    clean_queries = list(
        dict.fromkeys(query.strip() for query in queries if query.strip())
    )[:12]
    desired_jobs = max(1, min(desired_jobs, MAX_LIST_SIZE))
    inspection_limit = min(
        MAX_INSPECTION_CANDIDATES,
        max(MIN_INSPECTION_CANDIDATES, desired_jobs * CANDIDATE_MULTIPLIER),
    )
    results_per_query = min(
        MAX_WEB_RESULTS,
        max(8, math.ceil(inspection_limit / max(1, len(clean_queries)))),
    )
    seen = _history_urls()
    candidates: list[dict[str, str]] = []

    search_semaphore = asyncio.Semaphore(3)

    async def run_search(query: str) -> list[dict[str, str]]:
        async with search_semaphore:
            return await search_web(query, max_results=results_per_query)

    raw_result_groups = await asyncio.gather(
        *(run_search(query) for query in clean_queries)
    )
    listing_tasks: dict[str, asyncio.Task[list[dict[str, str]]]] = {}

    async def expand_listing(url: str) -> list[dict[str, str]]:
        task = listing_tasks.get(url)
        if task is None:
            task = asyncio.create_task(
                extract_job_links_from_listing(
                    url,
                    max_links=results_per_query * 2,
                )
            )
            listing_tasks[url] = task
        return await task

    async def expand_group(
        query: str,
        results: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        expanded: list[dict[str, str]] = []
        listing_pages_used = 0
        for result in results:
            if not looks_like_listing_url(result.get("url", "")):
                expanded.append({**result, "matched_query": query})
                continue

            if listing_pages_used >= MAX_LISTING_PAGES_PER_QUERY:
                continue
            listing_pages_used += 1
            direct_jobs = await expand_listing(result["url"])
            expanded.extend(
                {**job, "matched_query": query}
                for job in direct_jobs
            )
        return expanded

    result_groups = await asyncio.gather(
        *(
            expand_group(query, results)
            for query, results in zip(clean_queries, raw_result_groups)
        )
    )

    # Interleave queries so an early broad query cannot consume the entire
    # inspection budget before separate profile tracks are represented.
    for result_round in zip_longest(*result_groups):
        for result in result_round:
            if result is None:
                continue
            url = result.get("url", "")
            normalised = _normalise_url(url)
            if not url or normalised in seen:
                continue
            seen.add(normalised)
            candidates.append(result)
            if len(candidates) >= inspection_limit:
                break
        if len(candidates) >= inspection_limit:
            break

    semaphore = asyncio.Semaphore(4)

    async def inspect(candidate: dict[str, str]) -> dict[str, str] | None:
        async with semaphore:
            evidence = await inspect_job_page(candidate["url"])
        if evidence.get("status") not in {"active", "likely_active"}:
            return None
        return {
            "title": evidence.get("title") or candidate.get("title", ""),
            "url": evidence.get("final_url") or candidate["url"],
            "search_description": candidate.get("description", "")[:400],
            "matched_query": candidate.get("matched_query", ""),
            "page_title": evidence.get("page_title", ""),
            "status": evidence.get("status", ""),
            "verification": evidence.get("reason", ""),
            "date_posted": evidence.get("date_posted", ""),
            "valid_through": evidence.get("valid_through", ""),
            "content_excerpt": evidence.get("content", "")[:1000],
        }

    checked = await asyncio.gather(*(inspect(item) for item in candidates))
    verified_limit = min(
        MAX_VERIFIED_CANDIDATES,
        max(desired_jobs + 10, desired_jobs * 3),
    )
    return [item for item in checked if item is not None][:verified_limit]
