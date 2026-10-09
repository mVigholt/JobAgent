import csv
from pathlib import Path

from settings import (
    DATA_DIR,
    EXCLUDED_JOBS_FILE,
    EXCLUDED_JOBS_HEADERS,
    MAX_SAVED_SEARCHES,
    SAVED_SEARCHES_FILE,
    SAVED_SEARCHES_HEADERS,
    SUBMITTED_JOBS_FILE,
    SUBMITTED_JOBS_HEADERS,
)


def initialise_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        (SUBMITTED_JOBS_FILE, SUBMITTED_JOBS_HEADERS),
        (EXCLUDED_JOBS_FILE, EXCLUDED_JOBS_HEADERS),
        (SAVED_SEARCHES_FILE, SAVED_SEARCHES_HEADERS),
    ]

    for file_path, headers in files:
        if not file_path.exists():
            with file_path.open("w", newline="", encoding="utf-8") as file:
                csv.writer(file).writerow(headers)


def load_rows(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        return []

    with file_path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def append_row(
    file_path: Path,
    headers: list[str],
    row: dict[str, str],
) -> None:
    with file_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writerow(row)


def rewrite_rows(
    file_path: Path,
    headers: list[str],
    rows: list[dict[str, str]],
) -> None:
    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def get_saved_searches() -> list[dict[str, str]]:
    return load_rows(SAVED_SEARCHES_FILE)


def save_search(search: dict[str, str]) -> tuple[bool, str]:
    searches = get_saved_searches()

    if len(searches) >= MAX_SAVED_SEARCHES:
        return False, (
            f"Du har allerede {MAX_SAVED_SEARCHES} gemte søgninger. "
            "Slet en eksisterende søgning først."
        )

    append_row(SAVED_SEARCHES_FILE, SAVED_SEARCHES_HEADERS, search)
    return True, "Søgningen er gemt."


def get_saved_search_by_number(number: int) -> dict[str, str] | None:
    searches = get_saved_searches()
    index = number - 1

    if index < 0 or index >= len(searches):
        return None

    return searches[index]


def delete_saved_search(number: int) -> tuple[bool, str]:
    searches = get_saved_searches()
    index = number - 1

    if index < 0 or index >= len(searches):
        return False, "Ugyldigt søgenummer."

    searches.pop(index)
    rewrite_rows(SAVED_SEARCHES_FILE, SAVED_SEARCHES_HEADERS, searches)
    return True, "Søgningen blev slettet."


def get_submitted_jobs() -> list[dict[str, str]]:
    return load_rows(SUBMITTED_JOBS_FILE)


def get_excluded_jobs() -> list[dict[str, str]]:
    return load_rows(EXCLUDED_JOBS_FILE)


def register_submitted_job(job: dict[str, str]) -> None:
    append_row(SUBMITTED_JOBS_FILE, SUBMITTED_JOBS_HEADERS, job)


def register_excluded_job(job: dict[str, str]) -> None:
    append_row(EXCLUDED_JOBS_FILE, EXCLUDED_JOBS_HEADERS, job)
