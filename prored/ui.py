"""Additional workflow screens layered onto the original Stage 1 intake."""
import hashlib
import json
import os
import time
from pathlib import Path

import streamlit as st

from prored.assessment import Assessment
from prored.demo import MockProvider, demo_profile, demo_snapshot
from prored.github import GitHubClient, GitHubError, MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES
from prored.intake import IntakeError, normalize_skills, validate_github_url
from prored.provider import GroqProvider, ProviderError
from prored.service import Service, build_report, source_payload
from prored.sources import MAX_SNIPPET_CONTEXT, MAX_SNIPPETS, verified_source

WORKFLOW_KEYS = ["profile_scan", "profile_key", "snapshot", "snapshot_key", "comparison", "assessment", "assessment_inputs", "report", "confirmed_repository"]


def invalidate_workflow(keep_snapshot=False):
    for key in WORKFLOW_KEYS:
        if not keep_snapshot or key not in {"snapshot", "snapshot_key", "confirmed_repository", "profile_scan", "profile_key"}:
            st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("response_"):
            st.session_state.pop(key, None)


def action(operation):
    try:
        with st.spinner("Processing…"):
            return operation()
    except (IntakeError, GitHubError, ProviderError, ValueError) as error:
        st.error(str(error))
        return None


def ai(operation):
    provider = MockProvider() if st.session_state.get("ai_mode", "Mock AI") == "Mock AI" else GroqProvider(json_only_schemas=st.session_state.setdefault("provider_formats", set()))
    try:
        cache = st.session_state.setdefault("ai_cache", {})
        return operation(Service(provider, cache))
    finally:
        if hasattr(provider, "close"):
            provider.close()


def mode_controls():
    default_real = os.getenv("PRORED_MODE", "mock").lower() == "real"
    st.selectbox("AI provider mode", ["Mock AI", "Real Groq"], index=1 if default_real else 0, key="ai_mode")
    st.selectbox("Repository data", ["Bundled mock repository", "Live GitHub"], index=1 if default_real else 0, key="repo_mode")
    signature = (st.session_state["ai_mode"], st.session_state["repo_mode"], os.getenv("GROQ_MODEL", ""))
    previous = st.session_state.get("mode_signature")
    if previous and previous != signature:
        invalidate_workflow()
        st.session_state.pop("ai_cache", None)
        st.session_state.pop("repo_cache", None)
        st.session_state.pop("provider_formats", None)
    st.session_state["mode_signature"] = signature
    if st.session_state["ai_mode"] == "Mock AI":
        st.warning("MOCK AI: illustrative deterministic results, not candidate evaluation.")
    else:
        st.caption("Groq model: " + (os.getenv("GROQ_MODEL") or "not configured"))
        if not os.getenv("GROQ_API_KEY") or not os.getenv("GROQ_MODEL"):
            st.warning("Configure GROQ_API_KEY and GROQ_MODEL on the server to use real AI.")
    if st.session_state["repo_mode"] == "Bundled mock repository":
        st.caption("Repository content is a bundled fixture. It does not represent the entered GitHub URL.")
    st.button("Load sample CV", help="Loads a synthetic PDF into this session and switches to Candidate.", on_click=load_sample)


def load_sample():
    st.session_state.pop("cv_upload", None)
    st.session_state["cv_data"] = (Path(__file__).resolve().parent.parent / "examples" / "sample_cv.pdf").read_bytes()
    st.session_state["cv_filename"] = "sample_cv.pdf"
    st.session_state["github_url"] = "https://github.com/prored-demo"
    st.session_state["candidate_claims"] = "Python\nTesting\nSQL"
    st.session_state["candidate_projects"] = "Inventory | Built a Python inventory function with validation and tests."
    st.session_state["view"] = "Candidate"
    st.session_state.pop("application_saved", None)
    invalidate_workflow()


def jd_suggestions(jd):
    if st.button("Suggest skills with AI", disabled=not jd.strip()):
        result = action(lambda: ai(lambda service: service.suggest(jd)))
        if result:
            st.session_state["suggested_skills"] = result.skills
    suggestions = st.session_state.get("suggested_skills", [])
    if suggestions:
        st.write("Suggestions for your review: " + ", ".join(suggestions))
        accepted = st.multiselect("Suggestions to add", suggestions, key="accepted_suggestions")
        if st.button("Add selected suggestions"):
            manual = st.session_state.get("manual_skills", "").splitlines()
            st.session_state["manual_skills"] = "\n".join(normalize_skills(manual + accepted))


def cv_suggestions(text):
    st.caption("Real AI extraction sends up to 20,000 characters of best-effort contact-redacted CV text to Groq. Review the editable text and remove unnecessary personal details first. Redaction is not guaranteed anonymization.")
    consent = st.checkbox("Allow sending reviewed content to the external AI provider", key="ai_consent")
    enabled = bool(text.strip()) and (st.session_state.get("ai_mode") == "Mock AI" or consent)
    if st.button("Extract CV skills and projects", disabled=not enabled):
        result = action(lambda: ai(lambda service: service.extract_cv(text)))
        if result:
            st.session_state["candidate_claims"] = "\n".join(result.skills)
            st.session_state["candidate_projects"] = "\n".join(p.name + " | " + p.description for p in result.projects)
            st.success("Extracted technical claims. Review and correct the fields below.")


def update_requirements(skills):
    old = st.session_state.get("requirements_signature")
    if old is not None and old != skills:
        invalidate_workflow()
    st.session_state["requirements_signature"] = list(skills)


def application_saved(application):
    signature = hashlib.sha256(json.dumps(application, sort_keys=True).encode()).hexdigest()
    if signature != st.session_state.get("saved_application_signature"):
        invalidate_workflow()
        st.session_state["saved_application_signature"] = signature


def show_source(snapshot, source_id):
    source = verified_source(snapshot, source_id)
    if source is None:
        st.caption("Unverified source reference omitted.")
        return
    st.caption(f"{source.kind} · {source.path}:{source.start}–{source.end} · {source.source_id}")
    st.code(source.text, language="python" if source.path.endswith(".py") else "text")
    if source.url:
        st.link_button("Open commit-pinned source", source.url)
    else:
        st.caption("Verified against the local mock fixture only; no GitHub evidence link.")


def fetch_cached(url, skills):
    if st.session_state.get("repo_mode") == "Bundled mock repository":
        return demo_snapshot(url)
    key = (url, tuple(skills))
    cache = st.session_state.setdefault("repo_cache", {})
    entry = cache.get(key)
    if entry and time.monotonic() - entry[0] < 300:
        return entry[1]
    client = GitHubClient(os.getenv("GITHUB_TOKEN", ""))
    try:
        snapshot = client.snapshot(url, skills)
        if len(cache) >= 8:
            cache.pop(next(iter(cache)))
        cache[key] = (time.monotonic(), snapshot)
        return snapshot
    finally:
        client.close()


def scan(url, skills):
    if st.session_state.get("repo_mode") == "Bundled mock repository":
        return demo_profile()
    client = GitHubClient(os.getenv("GITHUB_TOKEN", ""))
    try:
        return client.scan_profile(url, skills)
    finally:
        client.close()


def candidate_workflow():
    application = st.session_state.get("application_saved")
    if not application:
        return
    st.divider()
    st.header("Repository and assessment")
    st.caption("This workflow uses the last saved application. Save again to apply intake edits. Changing saved inputs or requirements clears the previous assessment.")
    skills = st.session_state.get("required_skills", [])
    if not skills:
        st.info("Ask the recruiter to select required skills first.")
        return
    target = validate_github_url(application["GitHub URL"])
    repo_url = target.url if target.repository else None
    profile_key = (target.url, tuple(skills), st.session_state.get("repo_mode"))
    if target.repository:
        st.caption("Direct repository URL: repository selection is bypassed.")
    else:
        if st.button("Find public repositories"):
            result = action(lambda: scan(target.url, skills))
            if result:
                invalidate_workflow()
                st.session_state["profile_scan"] = result
                st.session_state["profile_key"] = profile_key
        result = st.session_state.get("profile_scan") if st.session_state.get("profile_key") == profile_key else None
        if result:
            for limitation in result.limitations:
                st.caption(limitation)
            if result.repositories:
                by_url = {r.url: r for r in result.repositories}
                suggested = result.suggested_url
                if suggested:
                    st.info("Suggested: " + suggested + "\n\n" + by_url[suggested].explanation)
                selected_url = st.selectbox("Public repository to inspect", list(by_url), index=list(by_url).index(suggested) if suggested else 0)
                selected = by_url[selected_url]
                st.caption(selected.explanation + (" · Fork repository" if selected.fork else " · Non-fork; original authorship is not established."))
                st.caption("Selection prioritizes metadata/dependency relevance. Stars are not used as skill evidence.")
                if st.button("Confirm repository"):
                    invalidate_workflow(keep_snapshot=True)
                    st.session_state.pop("snapshot", None)
                    st.session_state["confirmed_repository"] = selected_url
                repo_url = st.session_state.get("confirmed_repository")
    if not repo_url:
        return
    st.write("Selected repository: " + repo_url)
    snapshot_key = (repo_url, tuple(skills), st.session_state.get("repo_mode"))
    if st.button("Fetch and inspect selected repository"):
        snapshot = action(lambda: fetch_cached(repo_url, skills))
        if snapshot:
            invalidate_workflow(keep_snapshot=True)
            st.session_state["snapshot"] = snapshot
            st.session_state["snapshot_key"] = snapshot_key
    snapshot = st.session_state.get("snapshot") if st.session_state.get("snapshot_key") == snapshot_key else None
    if not snapshot:
        return
    if snapshot.mock:
        st.warning("MOCK REPOSITORY: all snippets are from a bundled fixture; not evidence about the candidate's entered repository.")
    st.caption(f"Frozen commit: {snapshot.commit}. {len(snapshot.files)} files, {len(snapshot.sources)} selected snippets. Coverage is incomplete.")
    st.caption(f"Limits: {MAX_FILES} files, {MAX_FILE_BYTES:,} bytes/file, {MAX_TOTAL_BYTES:,} total bytes; up to {MAX_SNIPPETS} stored snippets and {MAX_SNIPPET_CONTEXT:,} stored snippet characters.")
    sent_sources = source_payload(snapshot)
    st.caption(f"Free-tier context selection: {len(sent_sources)} snippets / {sum(len(s['text']) for s in sent_sources):,} characters available to the model. Additional stored snippets may not be sent.")
    with st.expander("Inspected files and coverage"):
        st.write(list(snapshot.files))
        st.write(snapshot.skipped[:100] or ["No selected-file exclusions; snippet and repository coverage remain bounded."])
        if snapshot.tree_truncated:
            st.warning("GitHub returned a truncated tree; unlisted files could not be considered.")
    if not snapshot.sources:
        st.warning("No usable source snippets were found. Only general questions can be generated; repository evidence cannot be assessed.")
    project_lines = [line.strip() for line in application.get("Projects", "").splitlines() if line.strip()]
    selected_project = st.selectbox("Confirm the CV project matching this repository", ["No confirmed project match — exclude project claims"] + project_lines, key="matched_project")
    st.caption("The app cannot establish a project match automatically. Confirm only the relevant project; unrelated CV projects are excluded.")
    matched = None if selected_project.startswith("No confirmed project") else selected_project
    claims = [line.strip() for line in application["Candidate claims"].splitlines() if line.strip()]
    inputs = (tuple(skills), tuple(claims), matched, snapshot.repository, snapshot.commit, st.session_state.get("ai_mode"), snapshot.mock)
    if st.session_state.get("assessment_inputs") not in {None, inputs}:
        invalidate_workflow(keep_snapshot=True)
    allowed = st.session_state.get("ai_mode") == "Mock AI" or st.session_state.get("ai_consent", False)
    st.caption("Real AI receives selected repository snippets, reviewed technical claims, and submitted answers. Raw CV/contact details are excluded from grading prompts. Remove personal details from claims and answers before submitting.")
    already_prepared = st.session_state.get("assessment") is not None and st.session_state.get("assessment_inputs") == inputs
    if already_prepared:
        st.caption("The prepared interview is saved. Change saved inputs or reset the session to prepare a new one.")
    if st.button("Prepare evidence and interview", disabled=not allowed or already_prepared):
        def prepare():
            def operation(service):
                comparison = service.compare(snapshot, skills, claims, matched)
                assessment = service.plan(snapshot, skills, comparison)
                return comparison, assessment
            return ai(operation)
        prepared = action(prepare)
        if prepared:
            st.session_state["comparison"], st.session_state["assessment"] = prepared
            st.session_state["assessment_inputs"] = inputs
    assessment = st.session_state.get("assessment")
    if not assessment:
        return
    render_interview(assessment, snapshot, allowed)


def render_interview(assessment: Assessment, snapshot, allowed):
    st.subheader("Technical interview")
    if assessment.mode == "mock":
        st.warning("MOCK ASSESSMENT: heuristic reviews demonstrate the flow and must not be used for candidate decisions.")
    reviewed = sum(a.review is not None for a in assessment.attempts)
    st.caption(f"{reviewed} submissions reviewed. Two initial questions and one coding task, with at most one follow-up each.")
    current = assessment.current
    if current:
        item = current.item
        st.write(f"{item.skill} · {item.difficulty} · {'Follow-up' if current.parent_id else 'Initial item'}")
        st.caption("General skill question/task — repository evidence unavailable for this item." if item.general else "Grounded in inspected repository code.")
        st.write(item.prompt)
        if item.source_id:
            show_source(snapshot, item.source_id)
        response_key = "response_" + current.item_id
        if response_key not in st.session_state:
            st.session_state[response_key] = item.starter_code if item.kind == "coding" else ""
        answer = st.text_area("Coding submission" if item.kind == "coding" else "Your technical answer", key=response_key, height=240, max_chars=12_000)
        if item.kind == "coding":
            st.info("AI code review — code was not executed.")
        if st.button("Submit code" if item.kind == "coding" else "Submit answer", disabled=not allowed):
            result = action(lambda: ai(lambda service: (service.submit(assessment, snapshot, current.item_id, answer), True)[1]))
            if result:
                st.rerun()
    else:
        st.success("Assessment complete. The recruiter report is ready in the Recruiter view.")
        with st.expander("Completed assessment: expected answers and rubrics"):
            for attempt in assessment.attempts:
                st.write(attempt.item.prompt)
                st.write(attempt.item.expected_answer)
                st.write([r.model_dump() for r in attempt.item.rubric])
    for attempt in assessment.attempts:
        if attempt.review:
            with st.expander(f"Submitted {attempt.item_id} · {attempt.item.skill} · {attempt.item.difficulty}"):
                st.write(attempt.answer)
                st.write(attempt.review.summary)
                st.caption(attempt.review.uncertainty)
                # Detailed rubric observations stay out of the candidate view until completion.
                if assessment.complete:
                    st.write([o.model_dump() for o in attempt.review.observations])


def recruiter_report():
    assessment = st.session_state.get("assessment")
    if not assessment:
        return
    st.divider()
    st.header("Recruiter report")
    if not assessment.complete:
        st.info("Candidate assessment is in progress. The complete report will appear after all items and follow-ups are submitted.")
        return
    snapshot = st.session_state["snapshot"]
    application = st.session_state["application_saved"]
    skills, claims, matched, *_ = st.session_state["assessment_inputs"]
    report = build_report(list(skills), list(claims), matched, snapshot, st.session_state["comparison"], assessment)
    if report["mode"] == "mock" or report["mock_repository"]:
        st.warning("MOCK CONTENT: this report includes illustrative AI results and/or fixture repository data. It is not a real candidate assessment.")
    st.caption(f"Repository: {snapshot.repository} · commit {snapshot.commit}")
    st.caption("Claimed, Repo Evidence, and Demonstrated overlap. No overall score or hiring recommendation is generated.")
    for row in report["skills"]:
        with st.expander(row["skill"], expanded=True):
            st.subheader("Claimed")
            st.write(row["Claimed"] or ["No relevant explicit CV skill claim recorded."])
            if matched:
                st.caption("Confirmed relevant project context: " + matched)
            st.subheader("Repo Evidence")
            st.write(row["Repo Evidence"]["status"])
            st.write(row["Repo Evidence"]["explanation"])
            for reference in row["Repo Evidence"]["references"]:
                show_source(snapshot, reference["source_id"])
            st.subheader("Demonstrated")
            for attempt in row["Demonstrated"]:
                st.write(f"{attempt['kind']} · {attempt['difficulty']} · {'follow-up' if attempt['followup'] else 'initial'}")
                st.write(attempt["question"])
                st.code(attempt["answer"], language="python") if attempt["kind"] == "coding" else st.write(attempt["answer"])
                st.write(attempt["review"]["summary"])
                st.write(attempt["review"]["observations"])
                st.caption(attempt["review"]["uncertainty"])
            if not row["Demonstrated"]:
                st.caption("This skill was not directly interviewed in the three-item MVP. Human follow-up is required.")
            st.subheader("Uncertainties and human follow-up")
            st.write(row["uncertainties"])
    st.write(report["uncertainties"])
    for limitation in report["limitations"]:
        st.caption(limitation)
    with st.expander("Expected answers and stored rubrics"):
        for attempt in assessment.attempts:
            st.write({"item": attempt.item_id, "expected_answer": attempt.item.expected_answer, "rubric": [r.model_dump() for r in attempt.item.rubric]})
    st.download_button("Download report JSON", json.dumps(report, indent=2, ensure_ascii=False), file_name="prored-report.json", mime="application/json")
