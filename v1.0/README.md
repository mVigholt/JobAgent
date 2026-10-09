# Modular JobAgent

This version uses a bounded tool-calling Gemini agent. 

The agent plans the searches and judges relevance, while DuckDuckGo Search scraping library (ddgs) and ordinary Python perform the mechanical web requests and page verification in one combined tool call.

ddgs requires no API key.

## 

## File overview

* app.py 
  * Chainlit entry point and command routing.
* credentials.py
  * Loads, requests and persists the Google API key.
* error\_handling.py
  * Handles invalid keys, quotas and model errors.
* agents.py
  * Gemini agent, combined search tool and model configuration.
* job\_discovery.py
  * Batched searches, history filtering and verification.
* web\_search.py
  * DDGS integration.
* page\_inspection.py
  * Opens candidate URLs and checks activity evidence.
* storage.py
  * CSV creation, reading and writing.
* workflows.py
  * Chainlit search-creation and job-search flows.
* settings.py
  * Paths, headers, limits and model name.
* data/
  * Runtime CSV files.

## 

## Install and run

* Create and activate a virtual environment, then run:
  * pip install -r requirements.txt
* Start the application:
  * chainlit run app.py
* Start the application with wathcmode (Monitors code files and restarts on changes)
  * chainlit run app.py -w
* If .env does not contain GOOGLE\_API\_KEY, Chainlit asks for it when the chat
starts and creates or updates .env automatically:
You do not need to create or edit .env manually. 
On later starts, the saved key is loaded automatically. 
If Google rejects the key as invalid, Chainlit asks for a replacement and overwrites GOOGLE\_API\_KEY in .env. 
A 429 rate limit also offers another key, while explaining that it may be a per-minute
limit rather than an exhausted daily quota. 
If a new key is entered, it replaces the existing key in .env, leaving the response empty keeps the current key. The .env file is excluded from Git.

## 

## Main change from the old version

The agent plans four to twelve focused queries and sends all of them through one "find\_verified\_job\_candidates" tool call. 

"job\_discovery.py" runs the searches removes duplicate and previously handled URLs, and checks a bounded number of pages concurrently. 
Gemini then judges relevance and writes the answer.

Multiple educations and keywords are treated as a search portfolio rather than one giant AND query. 

The agent is instructed to create both combined searches and separate tracks for each important background, competence group, and related job family. 

Preferred platforms are preferences, not an exclusive whitelist. 

Round-robin scheduling is used for search results, so an early broad query cannot consume the complete candidate budget and suppress the separate tracks.

DDGS searches are limited to the latest month. 

Every candidate job must then be opened with "inspect\_job\_page". HTTP errors, expired structured deadlines and common inactive-job messages are rejected before Gemini may see a job.
Known search-result URL patterns (including Jobindex "jobsoegning") are opened as sources rather than returned as jobs. 

Direct advertisement links such as Jobindex "jobannonce" and LinkedIn "jobs/view" are extracted from their HTML and then inspected individually. 

If extraction fails because the portal blocks the request or renders links only with JavaScript, direct site-specific DDGS results remain the fallback. 

Redirects, website homepages, and pages with multiple structured "JobPosting" objects can never be returned as individual jobs.

If a recent DDGS search returns no results, the application retries with the
current year and finally without a time limit. 

A resultless DDGS attempt returns an empty list instead of stopping the complete agent run.

Every run has hard Pydantic AI limits of two model requests and one successful tool call. This prevents the uncontrolled tool loop from the original version, while retaining agent-controlled search planning and relevance assessment.

The page-inspection budget scales with the requested number of jobs instead of using a fixed candidate count: max(30, desired\_jobs \* 6), with a configurable absolute safety ceiling of 150 in "settings.py". Thus 5 requested jobs inspect up to 30 candidates, 10 inspect up to 60, and 20 inspect up to 120. The ceiling is a resource guard, not a relevance rule - Gemini still chooses the queries and decides which verified candidates are relevant. 

The validated requested count is supplied to the tool through Pydantic AI run context, so the model cannot accidentally change the user's candidate budget.

## 

## Accepted commands

Only these exact commands are accepted outside guided input flows:

* ny søgning
* gemte søgninger
* gentag søgning
* slet søgning

Any other message receives an immediate invalid-command response and is not
sent to Gemini.



## API quota behavior

The application uses one Google key at a time. 

Additional keys from the same Google project share the same quota and therefore do not extend the free allowance. The application lets you manually replace a quota-exhausted key, which is useful when the new key belongs to another project you are authorized to use. 

Confirmation of the saved replacement key is sent as a new message below the user's key input, so the conversation order remains clear.

