# Verification — 2026-10-09

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
