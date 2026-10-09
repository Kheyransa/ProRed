# ProRed v1.3

An end-to-end Streamlit hackathon demo comparing a candidate's **Claimed**, **Repo Evidence**, and **Demonstrated** technical skills. All six stages build on the original local PDF/intake foundation. These dimensions overlap; the app does not generate hire/reject recommendations, an overall candidate score, or percentage job fit. There is no self-practice mode.

## Install and launch

PowerShell, Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Open the localhost URL printed by Streamlit. An existing `.venv` can be reused. Mock mode works without credentials.

## Configuration

Copy `.env.example` to `.env` only if `.env` does not already exist; edit **`.env`**, never the example. `.env` is ignored by Git and loaded server-side with python-dotenv. Existing process environment variables take precedence. Restart the server after changing settings.

| Variable | Purpose |
| --- | --- |
| `PRORED_MODE` | `mock` (default) or `real`; sets the initial UI modes. |
| `GROQ_API_KEY` | Required for real AI; keep it server-side. |
| `GROQ_MODEL` | Required for real AI. Suggested: `openai/gpt-oss-120b`. |
| `GITHUB_TOKEN` | Optional for higher public GitHub API rate limits; never used to analyze private repos. |
| `PRORED_CONTEXT_CHARS` | Optional snippet context budget, default `6000`, clamped to `1000`–`24000`. Reduce for small free-tier quotas. |

Gemini was not configured in this project, so Groq is the single real provider. The recommended model was checked in [Groq's current models documentation](https://console.groq.com/docs/models). The app also checks `/models` before the first real generation. Documented supported models request strict schema output; other models use JSON object mode. If Groq reports a structured-generation failure, the one remaining attempt requests JSON object output from the same real model with local Pydantic/reference validation. There are at most two attempts, and no mock substitution. See [Groq structured outputs](https://console.groq.com/docs/structured-outputs). Account model availability and free-plan quotas can change; there is no automatic paid-plan setup.

## Mock versus real

The sidebar controls **AI provider mode** and **Repository data** independently:

- **Mock AI** uses deterministic fixture/keyword and answer-length heuristics to demonstrate the workflow. It cannot assess a real candidate. Every mock result/report is labeled.
- **Bundled mock repository** uses local illustrative code, regardless of the entered profile/repo, and never creates GitHub evidence links. The mock profile has two choices, including a documentation-only alternative.
- **Real Groq** sends JD, best-effort contact-redacted CV extraction text, or selected technical claims/snippets/answers to Groq when the associated action is used. CV/grading actions require the candidate consent checkbox. JD suggestions disclose the transfer directly.
- **Live GitHub** requests only `api.github.com` REST endpoints, freezes final content to a commit, and requires no AI key for repository browsing.

Changing modes, required skills, confirmed repo, confirmed project, or the saved application invalidates dependent assessments. Real errors are shown; the app never silently substitutes mock output. Save intake changes before preparing a new assessment. Repository snapshots are cached for five minutes in the session; the active assessment keeps its pinned snapshot. Successful AI contracts are cached per input/model within that session. Reset clears session data and these caches.

## Full demo walkthrough

1. For a reproducible mock demo, select **Mock AI** and **Bundled mock repository**. In **Recruiter**, click **Load demo vacancy**. It fills the editable title `Junior Python / FastAPI Developer`, the API-development job description, and exactly these skills: Python, FastAPI, SQL, Input validation, Error handling, Unit testing. It never changes AI/repository modes. Optionally use **Suggest skills with AI** → **Suggestions to add** → **Add selected suggestions**, or add skills manually; merged skills are deduplicated.
2. Click **Save vacancy and continue** once to save and open **Candidate**. Click **Load sample CV** in the sidebar, or upload `examples/sample_cv.pdf`. The sample is synthetic. Review/correct extracted text, then click **Extract CV skills and projects** if desired. Skills and project descriptions remain editable. Real mode requires provider configuration and the external-AI consent checkbox; manual review/correction also works.
3. Save the reviewed application. The profile URL leads to **Find public repositories**, a suggestion with its reasons, and a user-controlled choice. Click **Confirm repository**. A direct repository URL bypasses this selection step.
4. Click **Fetch and inspect selected repository**. Review the pinned commit, inspected/skipped files, limits, and mock/incomplete coverage labels.
5. Explicitly confirm the relevant CV project, or leave **No confirmed project match** to exclude project claims. Unrelated CV projects are not included in the comparison prompt.
6. Click **Prepare evidence and interview**. The app prepares evidence plus exactly two open-ended questions and one self-contained coding task, including hidden expected answers and rubrics.
7. Submit each answer with its button. A weak answer receives easier scaffolding, a partial answer a similar-level clarification, and a strong answer a harder extension. Each initial item has at most one follow-up, so at most six submissions. A follow-up is prepared before it is displayed. Answers and reviews survive reruns and view changes; duplicate submissions are rejected.
8. For code, edit the multiline starter-code field and click **Submit code**. The app displays **AI code review — code was not executed.** No repository or candidate code is executed, and no runtime/test-pass claim is made.
9. On completion, click **Open recruiter report**, or switch to **Recruiter** in the sidebar. Read each skill's Claimed, Repo Evidence, and Demonstrated observations, difficulty attempted, verified snippets, uncertainties, and human follow-up topics. Click **Download report JSON** if desired. Expected answers and rubrics become visible to the candidate only after completion.
10. Click **Reset session** to remove CV, claims, repo content, assessment, and caches from the app session.

For a real demo, select **Real Groq** and **Live GitHub** before loading the sample. **Load sample CV** then loads `examples/real_demo_cv.pdf` and the genuine public repository `https://github.com/pypa/sampleproject`; it does not change the modes. This packaging demo contains Python and tests, but does not establish FastAPI or SQL experience: unsupported vacancy skills should retain honest missing-evidence/general-question labels. Confirm the `sampleproject` project context when appropriate. A direct URL skips profile selection. To check a live profile instead, enter `https://github.com/pypa`, save, find repos, select `sampleproject` if listed, or manually enter its direct URL if outside the bounded list. Exclude the CV project match if a different repo is selected. The mock profile `https://github.com/prored-demo` is a fixture identifier, not a live demo profile.

Real AI requires usable `.env` credentials, a currently available `GROQ_MODEL`, and consent. The synthetic live flow was checked with `openai/gpt-oss-20b`; changing the sidebar mode never overrides your configured model. Profile scanning is public/owner-scoped and bounded; confirm the suggestion before inspecting. Non-fork status does not establish original authorship. Stars are not used as skill evidence.

## Status, saving and changes

The sidebar shows **Current mode: Mock / Real / Mixed**, sample-versus-Groq provider information, and the configured model name without credentials. The top of the page shows the next step. **How to use ProRed** explains the button order, sample PDFs/repos, report dimensions, and the difference between sample vacancy data and mock analysis. Unavailable actions show their missing prerequisite and are disabled. GitHub and AI actions show operation-specific progress, while real timeouts, invalid responses, and rate limits stay errors rather than fabricated mock results.

- Vacancy drafts are editable. Changing the title, JD, or required skills, or loading another demo vacancy, immediately clears the previous assessment/report and requires **Save vacancy and continue** again. Existing candidate intake can be reused after reviewing it.
- Editing CV text, technical claims, projects, or the GitHub URL immediately clears dependent results; **Save reviewed application** is needed before proceeding. Replacing/removing the uploaded PDF also clears old claims/projects/links. Unsaved edits never keep an old report active.
- Changing the selected repository clears the previous confirmation/snapshot/report; click **Confirm repository** before fetching. Changing the confirmed project clears the assessment and requires **Prepare evidence and interview** again.
- Interview answer drafts survive Recruiter/Candidate navigation. Ordinary reruns do not generate questions/reviews or refetch repositories. Already completed scan/fetch/prepare actions are disabled for the same inputs. Public profile/snapshot reads and successful AI contracts are cached in this session; vacancy context separates assessment cache entries.
- Reset clears saved vacancy, CV and uploads, claims, answers, reports and session caches. There is no permanent application/vacancy storage. Neither demo vacancy nor sample CV loading silently changes AI/repository modes.

## Bounds and verified references

- PDF: 10 MB, 30 pages, 100,000 extracted characters. No OCR; encrypted/scanned/malformed PDFs fail with an explanation.
- Profile: at most 40 public repositories across two pages, and dependency probes on at most six relevant non-forks (up to two filenames each).
- Repository: at most 12 files, 40,000 bytes/file, and 120,000 total bytes. README/dependency/Python source/test files are prioritized; known generated/vendor directories and symlinks are excluded. GitHub tree truncation and file exclusions are disclosed.
- Stored snippets: at most 48 snippets and 24,000 characters, at most four snippets/3,000 characters per file. The model receives a smaller selection (default 6,000 characters, configurable), prioritizing implementations. Answer review receives only the current item's source. CV extraction is capped at 20,000 contact-redacted characters, JD at 12,000, and each submitted answer at 12,000. Oversized model payloads are rejected.
- AI: 45-second request timeout, at most two malformed-output attempts, task-specific completion budgets (800–3,500 tokens) and low reasoning effort on documented compatible models. The app does not automatically retry quota/auth errors. GitHub requests time out after 20 seconds. Follow-ups default to one and can be set to zero in the assessment/service API; the MVP rejects limits above one.

Exact fetched file content is stored in memory. Python AST identifies functions/classes/imports/decorators without execution; line ranges come from those exact contents. Source IDs hash repo, commit, path, ranges, and snippet. Every displayed reference is revalidated. Links point to the frozen commit. Invalid model references are omitted, and unsupported findings are downgraded to Cannot assess. README/dependency-only support cannot become Supported implementation. Structural reference validation does not guarantee that the model's interpretation is accurate.

## Verification commands

Results and exact limits of the performed checks are recorded in [VERIFICATION.md](VERIFICATION.md), including the successful full real synthetic flow with `openai/gpt-oss-20b` and the separate `gpt-oss-120b` quota limitation.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pip check
# Optional, uses real network/API quota with synthetic data:
.\.venv\Scripts\python -m scripts.check_live --github --ai
# Additional optional real CV/comparison/interview/adaptive/report flow:
.\.venv\Scripts\python -m scripts.check_live --github --flow
# Optional bounded waits for free-tier rate limits in this verification script only:
.\.venv\Scripts\python -m scripts.check_live --github --flow --retry-rate
# Test a different currently available model without editing .env:
.\.venv\Scripts\python -m scripts.check_live --github --flow --retry-rate --model openai/gpt-oss-20b
# Real backend flow with all six demo vacancy skills and real_demo_cv.pdf:
.\.venv\Scripts\python -m scripts.check_live --github --flow --retry-rate --model openai/gpt-oss-20b --demo-vacancy
```

The automated suite covers existing intake behavior, PDF/URL errors, commit-pinned references and tamper detection, bounded GitHub pagination/rate-limit/redirect handling, provider schema/auth/timeout failures, atomic submissions, all adaptive paths, and a complete mock flow through the Streamlit screens including reset. Network checks are opt-in, not silently included in pytest. The live runner processes only synthetic CV/answer text and public code and does not save report/CV artifacts. Free-tier rate limits can interrupt a real flow; successful reviews remain cached and a failed follow-up leaves the current submission pending. Retry the same submit action after the displayed wait. Failed real output is never displayed as verified evidence. A schema-specific JSON-format fallback is remembered for the session/model after a structured-generation failure, avoiding repeatedly spending quota on the same failed format.

## Render preparation (not deployed)

`render.yaml` is ready for a Python Web Service; no external resources have been created. Connect your repository in Render and either import the Blueprint or set these commands manually:

```text
Build: pip install -r requirements.txt
Start: python -m streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false
Health check: /_stcore/health
```

Set `GROQ_API_KEY` as a Render secret, configure `GROQ_MODEL`, and optionally add `GITHUB_TOKEN`. Use `PRORED_MODE=mock` for an offline demonstration, or `real` for the real integration defaults. Never upload `.env`. Render supplies `PORT` to the start command; see [Render web services](https://render.com/docs/web-services) and [Blueprint configuration](https://render.com/docs/blueprint-spec). A restart/sleep/redeploy or lost browser connection can lose the session; this MVP has no database. Both views are a shared unauthenticated demo, so use synthetic data when hosting publicly.

## Modules and limitations

`app.py` retains intake/screens. `prored/intake.py` handles PDFs/URLs, `github.py` repository selection/fetching, `sources.py` exact references, `schemas.py` contracts, `provider.py` the Groq interface, `demo.py` explicit fixtures, `service.py` comparison/planning/review, `assessment.py` state transitions, and `ui.py` workflow/report screens.

CVs and personal data are not persisted by default; raw text remains visible to the recruiter in this shared local session. Reset is not secure-memory erasure and cannot delete content already sent to Groq. Contact/header removal is best effort, not guaranteed anonymization. Instructions in CV/repository/answer content are treated as untrusted data, but LLM prompt injection and inaccurate judgments remain possible. PDF limits are not hostile-PDF process isolation. Link extraction reads visible text, not hidden PDF hyperlink annotations. Mixed scanned/text PDFs can omit image text and reading order may need correction.

Repository/dependency keyword ranking is approximate; source-language coverage starts with Python. One repository cannot assess every CV project. Three initial interview items cannot directly cover every selected skill; unasked skills are explicitly labeled for human follow-up. General questions are labeled when code evidence is unavailable. A dependency does not demonstrate meaningful use, missing evidence is not a false claim, and code/replies do not establish authorship or overall proficiency. Adaptive paths are not comparable overall scores. Mock reviews are illustrations, not technical judgments. There are no accounts, separate backend, database, emails, payments, or execution sandbox.
