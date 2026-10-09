from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ENV_FILE = BASE_DIR / ".env"

SUBMITTED_JOBS_FILE = DATA_DIR / "submitted_jobs.csv"
EXCLUDED_JOBS_FILE = DATA_DIR / "excluded_jobs.csv"
SAVED_SEARCHES_FILE = DATA_DIR / "saved_searches.csv"
MODEL_NAME = "gemini-3.6-flash"

MAX_SAVED_SEARCHES = 10
DEFAULT_LIST_SIZE = 10
MAX_LIST_SIZE = 50
MAX_WEB_RESULTS = 20

# Resource budgets scale with the requested result count. The absolute ceiling
# prevents one search from opening an unbounded number of external pages.
MIN_INSPECTION_CANDIDATES = 30
CANDIDATE_MULTIPLIER = 6
MAX_INSPECTION_CANDIDATES = 150
MAX_VERIFIED_CANDIDATES = 75
MAX_LISTING_PAGES_PER_QUERY = 2

SUBMITTED_JOBS_HEADERS = [
    "title",
    "company",
    "address",
    "application_deadline",
    "url",
]

EXCLUDED_JOBS_HEADERS = SUBMITTED_JOBS_HEADERS + ["reason"]

SAVED_SEARCHES_HEADERS = [
    "experience_education",
    "location",
    "search_radius_type",
    "search_radius_value",
    "keywords",
    "preferred_platforms",
    "list_size",
]
