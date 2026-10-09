from dataclasses import replace

import pytest

from prored.assessment import Assessment, next_difficulty
from prored.demo import MockProvider, demo_snapshot
from prored.provider import ProviderError
from prored.schemas import Comparison, InterviewItem
from prored.service import Service, build_report, redact_cv
from prored.sources import Snapshot, build_sources, verified_source


def prepared():
    snapshot = demo_snapshot()
    service = Service(MockProvider())
    skills = ['Python', 'Testing', 'SQL']
    comparison = service.compare(snapshot, skills, skills, 'Inventory | Python validation')
    assessment = service.plan(snapshot, skills, comparison)
    return snapshot, service, skills, comparison, assessment


def test_exact_sources_tamper_detection_and_commit_link():
    snapshot = demo_snapshot()
    sid = next(iter(snapshot.sources))
    source = verified_source(snapshot, sid)
    assert source and source.url is None
    snapshot.sources[sid] = replace(source, end=999)
    assert verified_source(snapshot, sid) is None
    snapshot.sources[sid] = source
    snapshot.files[source.path] = 'changed'
    assert verified_source(snapshot, sid) is None
    assert verified_source(snapshot, 'invented') is None
    real = Snapshot('https://github.com/alice/demo', 'b' * 40, {'a space.py': '@decorator\ndef f():\n    return 1\n'})
    build_sources(real)
    function = next(s for s in real.sources.values() if s.start == 1 and s.end == 3)
    assert f"/blob/{'b' * 40}/a%20space.py#L1-L3" in function.url
    assert verified_source(real, function.source_id)


@pytest.mark.parametrize('level,expected', [('weak', 'easy'), ('partial', 'medium'), ('strong', 'hard')])
def test_adaptive_path(level, expected):
    assert next_difficulty('medium', level) == expected
    snapshot, service, _, _, assessment = prepared()
    answer = {'weak': 'Unsure', 'partial': 'A loop adds all values in the input collection.', 'strong': 'Validation handles an empty input and raises on negative values; edge cases need checks.'}[level]
    current = assessment.current
    service.submit(assessment, snapshot, current.item_id, answer)
    assert current.review.level == level
    assert assessment.current.parent_id == current.item_id
    assert assessment.current.item.difficulty == expected
    with pytest.raises(ProviderError, match='stale'):
        service.submit(assessment, snapshot, current.item_id, answer)
    service.submit(assessment, snapshot, assessment.current.item_id, answer)
    assert assessment.current.item_id == 'initial-2'


def test_full_mock_flow_report_and_bounded_followups():
    snapshot, service, skills, comparison, assessment = prepared()
    assert service.extract_cv('Python inventory project with SQL').projects
    assert service.suggest('Python SQL testing developer').skills == ['Python', 'SQL', 'Testing']
    while assessment.current:
        service.submit(assessment, snapshot, assessment.current.item_id, 'Discuss validation and edge cases; empty input returns zero and negatives raise.')
    assert assessment.complete and len(assessment.attempts) == 6
    assert sum(a.item.kind == 'coding' for a in assessment.attempts) == 2
    report = build_report(skills, skills, None, snapshot, comparison, assessment)
    assert report['mode'] == 'mock' and report['mock_repository'] and report['complete']
    assert len(report['skills']) == 3
    assert report['skills'][2]['Repo Evidence']['status'] == 'Not found in inspected files'
    assert report['skills'][2]['Demonstrated'] == []
    assert all(ref['url'] is None for row in report['skills'] for ref in row['Repo Evidence']['references'])


def test_unverified_model_references_omitted():
    class BadReference(MockProvider):
        def generate(self, task, payload, schema):
            result = super().generate(task, payload, schema)
            if schema is Comparison:
                for row in result.evidence:
                    row.source_ids = ['made-up-id']
                    row.status = 'Supported'
            return result
    snapshot = demo_snapshot()
    comparison = Service(BadReference()).compare(snapshot, ['Python'], ['Python'], None)
    assert comparison.evidence[0].status == 'Cannot assess'
    assert not comparison.evidence[0].source_ids


def test_provider_failure_keeps_submission_atomic():
    snapshot, _, _, _, assessment = prepared()
    class FailFollowup(MockProvider):
        def generate(self, task, payload, schema):
            if schema is InterviewItem:
                raise ProviderError('followup failed')
            return super().generate(task, payload, schema)
    item_id = assessment.current.item_id
    with pytest.raises(ProviderError):
        Service(FailFollowup()).submit(assessment, snapshot, item_id, 'Meaningful response about validation and edge cases')
    assert assessment.current.item_id == item_id
    assert assessment.current.answer is None and assessment.current.review is None
    assert len(assessment.attempts) == 3


def test_contact_redaction_and_no_unrelated_project_prompt():
    assert 'alice@example.com' not in redact_cv('Alice Smith\nalice@example.com\nPython project\nPhone: +994 50 123 45 67')
    class Capture(MockProvider):
        def generate(self, task, payload, schema):
            self.payload = payload
            return super().generate(task, payload, schema)
    provider = Capture()
    Service(provider).compare(demo_snapshot(), ['Python'], ['Python', 'Unrelated React project'], None)
    assert provider.payload['claims'] == ['Python']


def test_semantically_invalid_output_does_not_poison_retry_cache():
    from prored.schemas import InterviewPlan
    class BadFirstPlan(MockProvider):
        count = 0
        def generate(self, task, payload, schema):
            result = super().generate(task, payload, schema)
            if schema is InterviewPlan:
                self.count += 1
                if self.count == 1:
                    result.items[0].source_id = 'invented'
            return result
    snapshot = demo_snapshot()
    provider = BadFirstPlan()
    service = Service(provider)
    comparison = service.compare(snapshot, ['Python'], ['Python'], None)
    with pytest.raises(ProviderError):
        service.plan(snapshot, ['Python'], comparison)
    assessment = service.plan(snapshot, ['Python'], comparison)
    assert provider.count == 2 and assessment.current
