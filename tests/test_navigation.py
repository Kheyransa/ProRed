"""Real Streamlit reruns/callbacks with synthetic inputs, not browser automation."""
import pytest
from streamlit.testing.v1 import AppTest

from prored.demo import MockProvider, demo_snapshot
from prored.service import Service
from prored.vacancy import DEMO_TITLE, DEMO_DESCRIPTION, DEMO_SKILLS


def app_start():
    return AppTest.from_file('../app.py', default_timeout=10).run()


def button(app, label):
    return next(b for b in app.button if b.label == label)


def click(app, label):
    button(app, label).click().run()
    assert not app.exception


def setup(app, profile=True):
    click(app, 'Load demo vacancy')
    click(app, 'Save vacancy and continue')
    assert app.sidebar.radio[0].value == 'Candidate'
    click(app, 'Load sample CV')
    if not profile:
        app.text_input(key='github_url').set_value('https://github.com/prored-demo/python-inventory').run()
    click(app, 'Save reviewed application')
    if profile:
        click(app, 'Find public repositories')
        click(app, 'Confirm repository')
    click(app, 'Fetch and inspect selected repository')
    click(app, 'Prepare evidence and interview')


@pytest.mark.parametrize('mode,repository_mode', [('Mock AI', 'Bundled mock repository'), ('Real Groq', 'Live GitHub'), ('Real Groq', 'Bundled mock repository'), ('Mock AI', 'Live GitHub')])
def test_demo_vacancy_is_editable_deduplicated_and_does_not_change_mode(mode, repository_mode):
    app = app_start()
    app.selectbox(key='ai_mode').set_value(mode).run()
    app.selectbox(key='repo_mode').set_value(repository_mode).run()
    app.text_area(key='manual_skills').set_value('Python\npython\nSQL').run()
    click(app, 'Load demo vacancy')
    assert app.selectbox(key='ai_mode').value == mode
    assert app.selectbox(key='repo_mode').value == repository_mode
    assert app.text_input(key='job_title').value == DEMO_TITLE
    assert app.text_area(key='job_description').value == DEMO_DESCRIPTION
    assert app.multiselect(key='selected_skills').value == DEMO_SKILLS
    assert app.session_state['required_skills'] == DEMO_SKILLS
    assert app.text_area(key='manual_skills').value == ''
    app.text_input(key='job_title').set_value('Edited vacancy').run()
    app.text_area(key='manual_skills').set_value('python\nDocker').run()
    assert app.session_state['required_skills'] == DEMO_SKILLS + ['Docker']
    click(app, 'Save vacancy and continue')
    assert app.session_state['vacancy_saved']['title'] == 'Edited vacancy'


@pytest.mark.parametrize('change', ['title', 'description', 'skills', 'demo'])
def test_vacancy_changes_clear_completed_report(change):
    app = app_start()
    setup(app, profile=False)
    assessment = app.session_state['assessment']
    service = Service(MockProvider())
    while assessment.current:
        service.submit(assessment, app.session_state['snapshot'], assessment.current.item_id, 'Validation and edge cases: empty inputs and values that raise errors.')
    app.sidebar.radio[0].set_value('Recruiter').run()
    assert any(h.value == 'Recruiter report' for h in app.header)
    if change == 'demo':
        click(app, 'Load demo vacancy')
    elif change == 'title':
        app.text_input(key='job_title').set_value('Other title').run()
    elif change == 'description':
        app.text_area(key='job_description').set_value('Different job, same skills').run()
    else:
        app.text_area(key='manual_skills').set_value('Docker').run()
    assert not app.exception
    assert 'assessment' not in app.session_state
    assert 'vacancy_saved' not in app.session_state
    assert not any(h.value == 'Recruiter report' for h in app.header)
    click(app, 'Save vacancy and continue')
    assert 'assessment' not in app.session_state


@pytest.mark.parametrize('key,value', [('cv_text', 'Corrected synthetic Python CV'), ('candidate_claims', 'Python\nSQL\nFastAPI'), ('candidate_projects', 'Other project | unrelated'), ('github_url', 'https://github.com/alice/another')])
def test_unsaved_candidate_edits_clear_assessment_and_require_save(key, value):
    app = app_start()
    setup(app, profile=False)
    if key == 'github_url':
        app.text_input(key=key).set_value(value).run()
    else:
        app.text_area(key=key).set_value(value).run()
    assert not app.exception
    assert app.session_state['application_dirty']
    assert 'assessment' not in app.session_state
    assert not any(b.label == 'Prepare evidence and interview' for b in app.button)
    click(app, 'Save reviewed application')
    assert not app.session_state['application_dirty']


def test_repository_change_requires_confirmation_and_clears_results():
    app = app_start()
    setup(app)
    app.selectbox(key='repository_choice').set_value('https://github.com/prored-demo/docs').run()
    assert 'assessment' not in app.session_state
    assert 'snapshot' not in app.session_state
    assert 'confirmed_repository' not in app.session_state
    assert not any(b.label == 'Fetch and inspect selected repository' for b in app.button)
    click(app, 'Confirm repository')
    click(app, 'Fetch and inspect selected repository')
    assert app.session_state['snapshot'].repository.endswith('/docs')
    assert list(app.session_state['snapshot'].files) == ['README.md']


def test_response_draft_survives_views_and_reruns_without_duplicate_ai_calls(monkeypatch):
    calls = []
    original = MockProvider.generate
    def counted(self, task, payload, schema):
        calls.append(schema.__name__)
        return original(self, task, payload, schema)
    monkeypatch.setattr(MockProvider, 'generate', counted)
    app = app_start()
    setup(app, profile=False)
    assert calls == ['Comparison', 'InterviewPlan']
    assert button(app, 'Submit answer').disabled
    app.text_area(key='response_initial-1').set_value('A draft answer').run()
    app.sidebar.radio[0].set_value('Recruiter').run()
    app.sidebar.radio[0].set_value('Candidate').run()
    assert app.text_area(key='response_initial-1').value == 'A draft answer'
    app.run()
    assert calls == ['Comparison', 'InterviewPlan']
    assert button(app, 'Prepare evidence and interview').disabled
    assert button(app, 'Fetch and inspect selected repository').disabled
    click(app, 'Submit answer')
    assert app.session_state['assessment'].current.item.difficulty == 'easy'
    app.run()
    assert calls == ['Comparison', 'InterviewPlan', 'Review', 'InterviewItem']


def test_real_actions_missing_config_or_consent_are_disabled(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', '')
    monkeypatch.setenv('GROQ_MODEL', '')
    app = app_start()
    app.selectbox(key='ai_mode').set_value('Real Groq').run()
    click(app, 'Load demo vacancy')
    assert button(app, 'Suggest skills with AI').disabled
    click(app, 'Save vacancy and continue')
    click(app, 'Load sample CV')
    assert button(app, 'Extract CV skills and projects').disabled
    click(app, 'Save reviewed application')
    click(app, 'Find public repositories')
    click(app, 'Confirm repository')
    click(app, 'Fetch and inspect selected repository')
    assert button(app, 'Prepare evidence and interview').disabled
    assert any('GROQ_API_KEY' in caption.value for caption in app.caption)


def test_real_sample_uses_a_public_url_and_does_not_switch_modes():
    app = app_start()
    app.selectbox(key='ai_mode').set_value('Real Groq').run()
    app.selectbox(key='repo_mode').set_value('Live GitHub').run()
    click(app, 'Load demo vacancy')
    click(app, 'Save vacancy and continue')
    click(app, 'Load sample CV')
    assert app.session_state['cv_filename'] == 'real_demo_cv.pdf'
    assert app.text_input(key='github_url').value == 'https://github.com/pypa/sampleproject'
    assert 'sampleproject' in app.text_area(key='cv_text').value
    assert app.selectbox(key='ai_mode').value == 'Real Groq'
    assert app.selectbox(key='repo_mode').value == 'Live GitHub'


def test_removed_pdf_clears_application_claims_and_results(monkeypatch):
    from prored import ui
    state = {'uploader': None, 'cv_data': b'old', 'cv_digest': 'old', 'application_saved': {}, 'assessment': object(), 'candidate_claims': 'old claim', 'candidate_projects': 'old project'}
    monkeypatch.setattr(ui.st, 'session_state', state)
    ui.upload_changed('uploader')
    assert 'cv_data' not in state and 'assessment' not in state
    assert 'application_saved' not in state
    assert state['candidate_claims'] == '' and state['candidate_projects'] == ''


@pytest.mark.parametrize('profile', [True, False])
def test_complete_demo_vacancy_ui_flow_easier_and_harder_paths(profile):
    app = app_start()
    setup(app, profile=profile)
    assert app.session_state['required_skills'] == DEMO_SKILLS
    reached = []
    for _ in range(6):
        current = app.session_state['assessment'].current
        reached.append((current.item_id, current.item.difficulty))
        answer = 'Unsure' if current.item_id == 'initial-1' else 'Explain validation and edge cases. Empty input returns zero; invalid values raise errors.'
        if current.item.kind == 'coding':
            answer = 'def safe_total(items):\n    # empty input\n    total = 0\n    for price in items:\n        if price < 0:\n            raise ValueError("negative")\n        total += price\n    return total'
        app.text_area(key='response_' + current.item_id).set_value(answer).run()
        click(app, 'Submit code' if current.item.kind == 'coding' else 'Submit answer')
    assert ('initial-1-followup', 'easy') in reached
    assert ('initial-2-followup', 'hard') in reached
    assert app.session_state['assessment'].complete
    click(app, 'Open recruiter report')
    assert any(h.value == 'Recruiter report' for h in app.header)
    assert sum(s.value == 'Claimed' for s in app.subheader) == 6
    assert sum(s.value == 'Repo Evidence' for s in app.subheader) == 6
    assert sum(s.value == 'Demonstrated' for s in app.subheader) == 6
    click(app, 'Reset session')
    assert 'assessment' not in app.session_state and 'vacancy_saved' not in app.session_state


def test_new_pdf_clears_previous_extracted_claims_and_projects():
    from test_intake import sample_pdf
    app = app_start()
    setup(app, profile=False)
    app.session_state['cv_data'] = sample_pdf('New synthetic CV: Python https://github.com/alice/demo')
    app.session_state['cv_filename'] = 'new.pdf'
    app.run()
    assert not app.exception
    assert app.text_area(key='candidate_claims').value == ''
    assert app.text_area(key='candidate_projects').value == ''
    assert app.text_input(key='github_url').value == ''
    assert 'application_saved' not in app.session_state and 'assessment' not in app.session_state


def test_real_provider_failure_keeps_mode_and_never_inserts_mock_results(monkeypatch):
    from prored import ui
    from prored.provider import ProviderError
    class FailingRealProvider:
        mode = 'real'
        model = 'test-model'
        def __init__(self, **kwargs):
            pass
        def generate(self, *args):
            raise ProviderError('Synthetic timeout: retry this action after checking the provider.')
        def close(self):
            pass
    app = app_start()
    setup(app, profile=False)
    monkeypatch.setenv('GROQ_API_KEY', 'synthetic-key-not-a-secret')
    monkeypatch.setenv('GROQ_MODEL', 'test-model')
    monkeypatch.setattr(ui, 'GroqProvider', FailingRealProvider)
    app.selectbox(key='ai_mode').set_value('Real Groq').run()
    app.checkbox(key='ai_consent').set_value(True).run()
    click(app, 'Find public repositories') if any(b.label == 'Find public repositories' for b in app.button) else None
    click(app, 'Fetch and inspect selected repository')
    click(app, 'Prepare evidence and interview')
    assert app.error and 'Synthetic timeout' in app.error[0].value
    assert app.selectbox(key='ai_mode').value == 'Real Groq'
    assert 'assessment' not in app.session_state and 'comparison' not in app.session_state


def test_existing_session_without_a_saved_vacancy_does_not_show_legacy_results():
    app = app_start()
    setup(app, profile=False)
    del app.session_state['vacancy_saved']
    app.run()
    assert not app.exception
    assert 'assessment' not in app.session_state
    assert not any(b.label == 'Prepare evidence and interview' for b in app.button)
    assert any('not linked to a saved vacancy' in item.value for item in app.info)
