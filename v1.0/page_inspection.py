import json
from datetime import date, timedelta
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


INACTIVE_PHRASES = {
    "stillingen er besat",
    "stillingen er ikke længere ledig",
    "jobbet er udløbet",
    "jobopslaget er udløbet",
    "ansøgningsfristen er udløbet",
    "denne stilling er ikke længere tilgængelig",
    "this job is no longer available",
    "this position is no longer available",
    "this job has expired",
    "the application deadline has passed",
    "position has been filled",
    "job posting has expired",
}


LISTING_PATH_MARKERS = {
    "/jobsoegning",
    "/jobsøgning",
    "/jobs/search",
    "/job-search",
    "/search/jobs",
    "/job-search-results",
}
DIRECT_JOB_PATH_MARKERS = {
    "/jobannonce/",
    "/jobs/view/",
}


def looks_like_listing_url(url: str) -> bool:
    try:
        path = unquote(urlsplit(url).path).casefold()
    except ValueError:
        return True
    return any(marker in path for marker in LISTING_PATH_MARKERS)


def _looks_like_direct_job_url(url: str) -> bool:
    try:
        path = unquote(urlsplit(url).path).casefold()
    except ValueError:
        return False
    return any(marker in path for marker in DIRECT_JOB_PATH_MARKERS)


def _find_job_postings(
    value: Any,
    results: list[dict[str, Any]],
) -> None:
    if isinstance(value, dict):
        item_type = value.get("@type")
        if item_type == "JobPosting" or (
            isinstance(item_type, list) and "JobPosting" in item_type
        ):
            results.append(value)

        for child in value.values():
            _find_job_postings(child, results)

    if isinstance(value, list):
        for child in value:
            _find_job_postings(child, results)


def _extract_job_metadata(soup: BeautifulSoup) -> dict[str, Any]:
    postings: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            parsed = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        _find_job_postings(parsed, postings)

    if not postings:
        return {
            "title": "",
            "date_posted": "",
            "valid_through": "",
            "job_posting_count": 0,
        }

    posting = postings[0]
    return {
        "title": str(posting.get("title", "")),
        "date_posted": str(posting.get("datePosted", "")),
        "valid_through": str(posting.get("validThrough", "")),
        "job_posting_count": len(postings),
    }


async def extract_job_links_from_listing(
    url: str,
    max_links: int = 20,
) -> list[dict[str, str]]:
    """Open a known job-list page and extract direct advertisement links."""
    if not looks_like_listing_url(url):
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    extracted: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        direct_url = urljoin(str(response.url), anchor.get("href", ""))
        if not _looks_like_direct_job_url(direct_url) or direct_url in seen:
            continue
        seen.add(direct_url)
        extracted.append(
            {
                "title": " ".join(anchor.get_text(" ", strip=True).split()),
                "url": direct_url,
                "description": "Udtrukket fra en joboversigt.",
            }
        )
        if len(extracted) >= max_links:
            break

    return extracted


def _date_part(value: str) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


async def inspect_job_page(url: str) -> dict[str, Any]:
    """Open a job URL and return evidence about whether it is still active."""
    if looks_like_listing_url(url):
        return {
            "url": url,
            "status": "unverifiable",
            "reason": "Linket er en jobsøgnings- eller oversigtsside.",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
            headers=headers,
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as error:
        return {
            "url": url,
            "status": "unverifiable",
            "reason": f"Siden kunne ikke hentes: {type(error).__name__}",
        }

    if response.status_code >= 400:
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "inactive",
            "reason": f"HTTP {response.status_code}",
        }

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "unverifiable",
            "reason": "Linket returnerede ikke en HTML-side.",
        }

    soup = BeautifulSoup(response.text, "html.parser")
    metadata = _extract_job_metadata(soup)

    final_path = response.url.path.rstrip("/")
    if not final_path:
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "unverifiable",
            "reason": "Linket endte på et websites forside, ikke et jobopslag.",
        }

    if looks_like_listing_url(str(response.url)):
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "unverifiable",
            "reason": "Linket endte på en jobsøgnings- eller oversigtsside.",
        }

    if metadata["job_posting_count"] > 1:
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "unverifiable",
            "reason": (
                "Siden indeholder flere jobopslag og er derfor en jobliste, "
                "ikke et direkte opslag."
            ),
        }

    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    text = " ".join(soup.get_text(" ", strip=True).split())
    lower_text = text.casefold()

    for phrase in INACTIVE_PHRASES:
        if phrase in lower_text:
            return {
                "url": url,
                "final_url": str(response.url),
                "http_status": response.status_code,
                "status": "inactive",
                "reason": f"Siden indeholder: '{phrase}'",
                **metadata,
            }

    deadline = _date_part(metadata["valid_through"])
    published = _date_part(metadata["date_posted"])
    if deadline is not None and deadline < date.today():
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "inactive",
            "reason": "Ansøgningsfristen er overskredet.",
            **metadata,
        }

    if (
        published is not None
        and published < date.today() - timedelta(days=90)
        and deadline is None
    ):
        return {
            "url": url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "status": "inactive",
            "reason": (
                "Opslaget er publiceret for mere end 90 dage siden, og der "
                "findes ingen fremtidig ansøgningsfrist."
            ),
            **metadata,
        }

    if deadline is not None:
        status = "active"
        reason = "JobPosting-data viser en fremtidig ansøgningsfrist."
    elif metadata["title"]:
        status = "likely_active"
        reason = "Siden indeholder JobPosting-data uden en verificerbar frist."
    else:
        status = "unverifiable"
        reason = "Ingen sikker aktivitetsstatus eller JobPosting-data fundet."

    return {
        "url": url,
        "final_url": str(response.url),
        "http_status": response.status_code,
        "status": status,
        "reason": reason,
        "page_title": soup.title.get_text(strip=True) if soup.title else "",
        "content": text[:1500],
        **metadata,
    }
