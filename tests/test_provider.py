import json

import httpx
import pytest

from prored.provider import GroqProvider, ProviderError, constrain_source_schema
from prored.schemas import SkillSuggestions, InterviewPlan, InterviewItem, Comparison


def provider(handler):
    return GroqProvider('test-key', 'openai/gpt-oss-120b', httpx.MockTransport(handler))


def models():
    return httpx.Response(200, json={'data': [{'id': 'openai/gpt-oss-120b'}]})


def test_real_provider_structured_format_and_model_check():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/models'):
            return models()
        body = json.loads(request.content)
        assert body['response_format']['json_schema']['strict'] is True
        assert 'untrusted' in body['messages'][0]['content']
        assert 'tools' not in body
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"skills":["Python"]}'}}]})
    client = provider(handler)
    try:
        assert client.generate('skills', {}, SkillSuggestions).skills == ['Python']
        assert len(calls) == 2
    finally:
        client.close()


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_provider_http_errors_do_not_fallback(status):
    client = provider(lambda request: httpx.Response(status))
    with pytest.raises(ProviderError):
        client.generate('skills', {}, SkillSuggestions)
    client.close()


def test_invalid_response_retries_are_bounded():
    count = 0
    def handler(request):
        nonlocal count
        if request.url.path.endswith('/models'):
            return models()
        count += 1
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"skills": "wrong"}'}}]})
    client = provider(handler)
    with pytest.raises(ProviderError, match='two attempts'):
        client.generate('skills', {}, SkillSuggestions)
    assert count == 2
    client.close()


def test_missing_credentials_unavailable_model_and_timeout():
    with pytest.raises(ProviderError, match='requires'):
        GroqProvider('', '')
    client = provider(lambda request: httpx.Response(200, json={'data': []}))
    with pytest.raises(ProviderError, match='not currently available'):
        client.generate('skills', {}, SkillSuggestions)
    client.close()
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    client = provider(timeout)
    with pytest.raises(ProviderError, match='timed out'):
        client.generate('skills', {}, SkillSuggestions)
    client.close()


def test_source_ids_are_constrained_in_model_schema():
    sources = [{'source_id': 'code', 'kind': 'Source implementation'}, {'source_id': 'readme', 'kind': 'README statement'}]
    plan = constrain_source_schema(InterviewPlan.model_json_schema(), sources)
    choices = plan['$defs']['InterviewItem']['properties']['source_id']['anyOf'][0]['enum']
    assert choices == ['code']
    comparison = constrain_source_schema(Comparison.model_json_schema(), sources)
    assert comparison['$defs']['Evidence']['properties']['source_ids']['items']['enum'] == ['code', 'readme']
    empty = constrain_source_schema(InterviewPlan.model_json_schema(), [])
    assert empty['$defs']['InterviewItem']['properties']['source_id']['type'] == 'null'
    constrained = constrain_source_schema(Comparison.model_json_schema(), sources, ['Python', 'Testing'])
    assert constrained['$defs']['Evidence']['properties']['skill']['enum'] == ['Python', 'Testing']
    assert constrained['properties']['evidence']['minItems'] == constrained['properties']['evidence']['maxItems'] == 2
    followup = constrain_source_schema(InterviewItem.model_json_schema(), sources, ['Python'])
    assert followup['properties']['general']['enum'] == [False]
    assert followup['properties']['source_id']['enum'] == ['code']
    general = constrain_source_schema(InterviewItem.model_json_schema(), [], ['Python'])
    assert general['properties']['general']['enum'] == [True]


def test_provider_json_generation_error_has_bounded_retries():
    count = 0
    def handler(request):
        nonlocal count
        if request.url.path.endswith('/models'):
            return models()
        count += 1
        return httpx.Response(400, json={'error': {'code': 'json_validate_failed'}})
    client = provider(handler)
    with pytest.raises(ProviderError, match='two attempts'):
        client.generate('skills', {}, SkillSuggestions)
    assert count == 2
    client.close()


def test_structured_failure_retries_json_from_same_real_provider():
    formats = []
    def handler(request):
        if request.url.path.endswith('/models'):
            return models()
        body = json.loads(request.content)
        formats.append(body['response_format']['type'])
        if len(formats) == 1:
            return httpx.Response(400, json={'error': {'code': 'json_validate_failed'}})
        assert 'Output schema:' in body['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"skills":["Python"]}'}}]})
    client = provider(handler)
    assert client.generate('skills', {}, SkillSuggestions).skills == ['Python']
    assert client.mode == 'real' and formats == ['json_schema', 'json_object']
    assert 'SkillSuggestions' in client.json_only_schemas
    client.generate('different skills', {}, SkillSuggestions)
    assert formats[-1] == 'json_object'
    client.close()
