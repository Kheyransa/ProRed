from streamlit.testing.v1 import AppTest


def test_views_requirements_url_and_reset():
    app = AppTest.from_file('../app.py', default_timeout=10).run()
    assert not app.exception
    app.text_area(key='job_description').set_value('Python developer')
    app.multiselect(key='selected_skills').set_value(['Python', 'Git'])
    app.text_area(key='manual_skills').set_value('SQL\nTesting\npython').run()
    assert app.session_state['required_skills'] == ['Python', 'Git', 'SQL', 'Testing']
    app.sidebar.radio[0].set_value('Candidate').run()
    assert not app.exception
    app.text_input(key='github_url').set_value('https://github.com/alice/demo').run()
    assert any('Repository URL format accepted' in item.value for item in app.success)
    app.text_input(key='github_url').set_value('https://example.com/alice').run()
    assert app.error
    app.sidebar.radio[0].set_value('Recruiter').run()
    assert app.text_area(key='job_description').value == 'Python developer'
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.text_area(key='job_description').value == ''


def test_candidate_pdf_review_save_and_view_switch():
    from test_intake import sample_pdf

    app = AppTest.from_file('../app.py', default_timeout=10).run()
    app.session_state['cv_data'] = sample_pdf('Python https://github.com/alice/demo')
    app.session_state['cv_filename'] = 'sample.pdf'
    app.sidebar.radio[0].set_value('Candidate').run()
    assert not app.exception
    assert 'Python' in app.text_area(key='cv_text').value
    next(button for button in app.button if button.label == 'Use selected link').click().run()
    app.text_area(key='cv_text').set_value('Corrected Python claim').run()
    next(button for button in app.button if button.label == 'Save reviewed application').click().run()
    assert app.session_state['application_saved']['CV text'] == 'Corrected Python claim'
    app.sidebar.radio[0].set_value('Recruiter').run()
    assert any('Candidate intake saved' in item.value for item in app.success)
    app.sidebar.radio[0].set_value('Candidate').run()
    assert app.text_area(key='cv_text').value == 'Corrected Python claim'
    assert not app.exception
