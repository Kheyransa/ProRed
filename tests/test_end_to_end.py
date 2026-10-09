from streamlit.testing.v1 import AppTest


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_full_mock_ui_flow_and_reset():
    app = AppTest.from_file('../app.py', default_timeout=10).run()
    app.text_area(key='job_description').set_value('Python testing and SQL developer').run()
    click(app, 'Suggest skills with AI')
    app.multiselect(key='accepted_suggestions').set_value(['Python', 'Testing', 'SQL']).run()
    click(app, 'Add selected suggestions')
    assert app.session_state['required_skills'] == ['Python', 'Testing', 'SQL']
    click(app, 'Load sample CV')
    assert app.sidebar.radio[0].value == 'Candidate'
    click(app, 'Extract CV skills and projects')
    assert 'Python' in app.text_area(key='candidate_claims').value
    click(app, 'Save reviewed application')
    click(app, 'Find public repositories')
    click(app, 'Confirm repository')
    click(app, 'Fetch and inspect selected repository')
    assert app.session_state['snapshot'].mock
    app.selectbox(key='matched_project').set_value(app.selectbox(key='matched_project').options[1]).run()
    click(app, 'Prepare evidence and interview')
    assert len(app.session_state['assessment'].attempts) == 3
    assert not any('Completed assessment:' in expander.label for expander in app.expander)
    for index in range(6):
        current = app.session_state['assessment'].current
        assert current is not None
        value = 'def safe_total(items):\n    # empty input and edge cases require validation\n    if any(price < 0 for price in items):\n        raise ValueError("negative")\n    return sum(items)' if current.item.kind == 'coding' else 'Explain validation, empty input, and edge cases; negative values raise errors.'
        app.text_area(key='response_' + current.item_id).set_value(value).run()
        click(app, 'Submit code' if current.item.kind == 'coding' else 'Submit answer')
    assert app.session_state['assessment'].complete
    app.run()
    assert len(app.session_state['assessment'].attempts) == 6
    app.sidebar.radio[0].set_value('Recruiter').run()
    assert not app.exception
    assert any(header.value == 'Recruiter report' for header in app.header)
    assert any(sub.value == 'Claimed' for sub in app.subheader)
    assert any(sub.value == 'Repo Evidence' for sub in app.subheader)
    assert any(sub.value == 'Demonstrated' for sub in app.subheader)
    click(app, 'Reset session')
    assert 'assessment' not in app.session_state
    assert 'cv_data' not in app.session_state
    assert 'ai_cache' not in app.session_state
