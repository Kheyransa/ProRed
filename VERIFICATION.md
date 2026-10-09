# Verification — 2026-10-09

## Follow-up: demo vacancy and workflow fixes

The current implementation was checked after adding **Load demo vacancy**, **Save vacancy and continue**, prerequisite/status messages, draft invalidation, persistent interview drafts, and mode-aware synthetic CV loading.

- **70 automated tests passed**: original tests retained (updated to save the vacancy prerequisite), plus all four AI/repository mode combinations for demo loading, editable/deduplicated skills, changed title/JD/skills clearing finished reports, unsaved CV/claims/projects/URL changes, repository re-confirmation, upload replacement/removal, missing real configuration/consent, preserved answer drafts, provider failure without mock substitution, cache separation by vacancy context, and legacy sessions lacking a saved vacancy.
- **Streamlit screen flows (AppTest, not a browser):** the six-skill demo vacancy completed through both direct-repository and profile-selection paths, all six submissions, an easier and a harder adaptive path, all report dimensions, and reset. Reruns made no extra mock-provider calls and incomplete actions were disabled.
- **Live backend integration:** `real_demo_cv.pdf`, all six demo-vacancy skills and saved JD context, real public `pypa/sampleproject` content at commit `621e4974ca25ce531773def586ba3ed8e736b3fc`, and Groq `openai/gpt-oss-20b` completed CV extraction, source-validated comparison, question/coding/rubric preparation, six reviews and the three-dimension report. Only synthetic data was used; no credentials, CV personal details or solutions were printed. The check process model override did not edit `.env`.
- **Rate limits:** encountered in the live run; the opt-in verification runner used bounded 30-second waits and kept completed steps cached. The app displays actionable errors and never switches to mock or commits a partial submission after a failed follow-up.
- **Local server:** health endpoint returned HTTP 200 / `ok`; package dependency check and Python compilation passed.
- **Browser flow not checked:** the Browser runtime reported `No browser is available`; its supported discovery returned an empty browser list. No browser clicks, screenshots, or actual browser PDF upload are claimed. Upload-removal behavior was checked through its callback and synthetic state, and PDF extraction with real synthetic PDF bytes.
- **Not checked/deployed:** Render deployment/Linux build and a real applicant assessment. Live profile ranking remains covered by controlled HTTP tests rather than a new live profile scan. The current live end-to-end check was a service-layer integration, not the unavailable real browser UI.

Command for the current live check:

```powershell
.\.venv\Scripts\python -m scripts.check_live --github --flow --retry-rate --model openai/gpt-oss-20b --demo-vacancy
```

## Earlier foundation checks

Performed in the project virtual environment on Windows with Python 3.13.15.

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 47 passed; includes the complete mock Streamlit UI flow and original Stage 1 tests. |
| `python -m pip check` | No broken requirements found. |
| Python compilation | `app.py`, `prored`, `scripts`, and tests compiled successfully. |
| Local Streamlit startup | Started at `http://127.0.0.1:8501`; `/_stcore/health` returned HTTP 200 / `ok`. |
| Live GitHub | Read `pypa/sampleproject` at commit `621e4974ca25ce531773def586ba3ed8e736b3fc`: 7 files, 13 locally verified source snippets, non-truncated tree. |
| Live Groq `openai/gpt-oss-120b` | Model availability, structured JD skill extraction, CV extraction, comparison, and interview preparation verified. Full review flow interrupted by free-tier limits. |
| Live Groq `openai/gpt-oss-20b` | Complete synthetic flow passed: CV claims, comparison/reference validation, two questions and one coding task with stored rubrics, all three adaptive follow-ups, six reviews, and three-dimension report. |

The full real check used:

```powershell
.\.venv\Scripts\python -m scripts.check_live --github --flow --retry-rate --model openai/gpt-oss-20b
```

Only synthetic CV/answer text and public repository code were sent. No repository or submitted code was executed, no test-pass/runtime assertion was made about candidate code, and no CV/report was persisted. Model override affected the check process only; local `.env` model selection was preserved.

Live testing exposed rate limits, structured-generation errors, and inconsistent references/general labels. These were rejected rather than saved as evidence. Request/format budgets, source/skill/adaptive schema constraints, same-provider JSON-format retry, session-scoped format memory, and invalid semantic-cache eviction were verified through focused tests and the final successful real run. The application does not silently replace real failures with mock results.

Profile pagination/ranking and source selection were covered with controlled GitHub HTTP transports and the mock UI flow. No Render deployment, Linux build, browser screenshot review, or real applicant assessment was performed. The shared-session app has no authentication; OCR and runtime execution are intentionally absent.

During configuration, credentials found in `.env.example` were moved into ignored `.env`, and the example restored to placeholders. Their values appeared in an earlier tool readout, so rotate those credentials before further use.
