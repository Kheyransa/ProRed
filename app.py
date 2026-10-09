"""Run with: python -m streamlit run app.py"""

import hashlib
import streamlit as st

from prored.intake import IntakeError, extract_github_links, extract_pdf_text, normalize_skills, validate_github_url
from prored import ui
from prored.config import load_config
from prored.vacancy import SKILL_OPTIONS

load_config()

st.set_page_config(page_title="ProRed v1.3", page_icon="🔎", layout="wide")
# Preserve editable fields when their widgets are hidden by the other view.
for field in ["job_title", "job_description", "selected_skills", "manual_skills", "cv_text", "candidate_claims", "candidate_projects", "github_url", "ai_consent", "matched_project", "accepted_suggestions"] + [key for key in st.session_state if key.startswith("response_")]:
    if field in st.session_state:
        st.session_state[field] = st.session_state[field]
st.title("ProRed")
st.caption("v1.3 · Evidence-grounded technical assessment")
st.info("Compare Claimed, Repo Evidence, and Demonstrated. AI observations support human assessment; no hiring recommendations or overall scores.")
status = st.container()
ui.how_to_use()

with st.sidebar:
    st.header("Demo workspace")
    view = st.radio("View", ["Recruiter", "Candidate"], key="view")
    st.caption("Both views share this browser session. There are no accounts or access controls.")
    st.caption("CV and assessment data stay in session memory. Real AI sends reviewed technical content to Groq with your consent. Reset clears session data and caches.")
    if st.button("Reset session", type="secondary"):
        upload_generation = st.session_state.get("upload_generation", 0) + 1
        for key in list(st.session_state):
            del st.session_state[key]
        st.session_state["upload_generation"] = upload_generation
        st.rerun()
    ui.mode_controls()

# Existing browser sessions from earlier versions must satisfy the new save gate.
if not st.session_state.get("vacancy_saved") and st.session_state.get("assessment"):
    ui.invalidate_workflow()
    ui.flash("Save the vacancy before preparing a new assessment. Previous results were cleared because they were not linked to a saved vacancy.")

if view == "Recruiter":
    st.header("Recruiter setup")
    st.button("Load demo vacancy", type="primary", on_click=ui.load_demo_vacancy)
    st.caption("Loads an editable sample vacancy only. AI/repository modes remain unchanged. Replacing a vacancy clears the previous assessment/report.")
    st.text_input("Job title", key="job_title")
    jd = st.text_area("Job description", key="job_description", height=220, placeholder="Paste the job requirements…")
    st.caption("Suggest skills sends the job description to Groq in real mode. Remove confidential or personal information first.")
    ui.jd_suggestions(jd)
    selected = st.multiselect("Required skills", SKILL_OPTIONS, key="selected_skills")
    manual = st.text_area("Additional skills (one per line)", key="manual_skills", placeholder="Docker\nREST APIs")
    skills = normalize_skills(selected + manual.splitlines())
    st.session_state["required_skills"] = skills
    vacancy = ui.draft_vacancy()
    ui.track_vacancy(vacancy)
    st.subheader("Requirements for review")
    if skills:
        st.write(", ".join(skills))
    else:
        st.caption("Select or add skills. There is no two-skill limit.")
    reasons = ([] if jd.strip() else ["enter a job description"]) + ([] if skills else ["select or add at least one required skill"])
    ui.disabled_reason(reasons)
    st.button("Save vacancy and continue", disabled=bool(reasons), on_click=ui.save_vacancy, type="primary")
    if st.session_state.get("vacancy_saved"):
        st.success("Vacancy saved. Candidate intake can continue.")
    if st.session_state.get("application_saved"):
        st.success("Candidate intake saved in this session.")
        with st.expander("Reviewed candidate application"):
            saved_application = st.session_state["application_saved"]
            st.write("GitHub: " + saved_application["GitHub URL"])
            st.write("Technical claims")
            st.text(saved_application["Candidate claims"])
            st.write("Projects")
            st.text(saved_application.get("Projects", ""))
            with st.expander("Reviewed CV text"):
                st.text(saved_application["CV text"])
    ui.recruiter_report()
else:
    st.header("Candidate application")
    saved_vacancy = st.session_state.get("vacancy_saved")
    if saved_vacancy:
        st.write("Vacancy: " + (saved_vacancy["title"] or "Custom vacancy"))
        with st.expander("Saved job description"):
            st.write(saved_vacancy["description"])
    skills = st.session_state.get("required_skills", [])
    st.write("Required skills: " + (", ".join(skills) if skills else "Recruiter has not set requirements yet."))
    if not st.session_state.get("vacancy_saved"):
        st.warning("First open Recruiter and click Save vacancy and continue. You can review a CV here, but cannot save or start assessment until the vacancy is saved.")
    st.caption("Upload a text-based PDF (up to 10 MB, 30 pages). Scanned PDFs and OCR are unsupported.")
    upload_key = f"cv_upload_{st.session_state.get('upload_generation', 0)}"
    uploaded = st.file_uploader("CV PDF", type=["pdf"], key=upload_key, on_change=ui.upload_changed, args=(upload_key,))
    if uploaded is not None:
        st.session_state["cv_data"] = uploaded.getvalue()
        st.session_state["cv_filename"] = uploaded.name
    data = st.session_state.get("cv_data")
    if data is not None:
        st.caption(f"Session CV: {st.session_state['cv_filename']}. Upload another PDF to replace it; Reset session removes it.")
        digest = hashlib.sha256(data).hexdigest()
        if digest != st.session_state.get("cv_digest"):
            ui.invalidate_workflow()
            st.session_state.pop("application_saved", None)
            st.session_state["cv_text"] = ""
            st.session_state["cv_error"] = ""
            if not st.session_state.pop("sample_pending", False):
                st.session_state.update(candidate_claims="", candidate_projects="", github_url="")
            try:
                st.session_state["cv_text"] = extract_pdf_text(data)
            except IntakeError as error:
                st.session_state["cv_error"] = str(error)
            st.session_state["cv_digest"] = digest
        if st.session_state.get("cv_error"):
            st.error(st.session_state["cv_error"])
    else:
        if st.session_state.pop("cv_digest", None) is not None:
            st.session_state.pop("cv_error", None)
            st.session_state.pop("application_saved", None)
        st.session_state["cv_text"] = ""
    text = st.text_area("Extracted CV text — review and correct", key="cv_text", height=280, disabled=data is None)
    ui.cv_suggestions(text)
    st.caption("Review extracted technical claims or enter them manually. Do not include unnecessary personal details.")
    claims = st.text_area("CV skill claims (editable; project descriptions below)", key="candidate_claims", height=120)
    projects = st.text_area("Projects (one per line: name | description)", key="candidate_projects", height=120)
    links = extract_github_links(text)
    st.subheader("GitHub links found in reviewed text")
    if links:
        st.write(links)
        choice = st.selectbox("Choose a detected link", links)
        if st.button("Use selected link"):
            st.session_state["github_url"] = choice
    else:
        st.caption("No supported profile/repository link found. Enter one manually below.")
    url = st.text_input("GitHub repository or profile URL", key="github_url", placeholder="https://github.com/username/repository")
    target = None
    if url.strip():
        try:
            target = validate_github_url(url)
            st.success(f"{target.kind} URL format accepted: {target.url}")
            st.caption("Existence and public access have not been checked yet. " + ("A direct repository bypasses selection." if target.repository else "After saving, find and confirm a public repository below."))
        except IntakeError as error:
            st.error(str(error))
    application = {"CV text": text, "Candidate claims": claims, "Projects": projects, "GitHub URL": target.url if target else url.strip(), "URL type": target.kind if target else "Invalid"}
    ui.track_application(application)
    reasons = ([] if st.session_state.get("vacancy_saved") else ["save the recruiter vacancy"]) + ([] if data is not None and text.strip() and not st.session_state.get("cv_error") else ["upload a readable PDF and review its text"]) + ([] if target else ["enter a valid GitHub profile or repository URL"])
    ui.disabled_reason(reasons)
    if st.button("Save reviewed application", type="primary", disabled=bool(reasons)):
        if data is None or st.session_state.get("cv_error") or not text.strip() or target is None:
            st.error("Upload a readable PDF, review its text, and enter a valid GitHub URL before saving.")
        else:
            ui.application_saved(application)
            st.session_state["application_saved"] = application
            st.success("Reviewed application saved for the recruiter in this session.")
    st.caption("Repository evidence does not establish authorship. No hiring recommendation is produced.")
    ui.candidate_workflow()

with status:
    notice = st.session_state.pop("workflow_notice", None)
    if notice:
        st.info(notice)
    ui.workflow_status()
