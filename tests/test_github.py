import base64
import json

import httpx
import pytest

from prored.github import GitHubClient, GitHubError
from prored.sources import verified_source

SHA = 'b' * 40
TREE = 'c' * 40
BLOB = 'd' * 40


def test_snapshot_is_pinned_and_exact_content_preserved():
    paths = []
    content = 'def total(items):\r\n    return sum(items)\r\n'
    def handler(request):
        paths.append(str(request.url))
        path = request.url.path
        if path == '/repos/alice/demo':
            data = {'default_branch': 'main', 'private': False}
        elif '/commits/' in path:
            data = {'sha': SHA, 'commit': {'tree': {'sha': TREE}}}
        elif '/git/trees/' in path:
            data = {'tree': [{'path': 'src/main.py', 'sha': BLOB, 'type': 'blob', 'mode': '100644', 'size': len(content)}, {'path': 'huge.py', 'type': 'blob', 'size': 999_999}], 'truncated': True}
        else:
            assert '/git/blobs/' + BLOB in path
            data = {'encoding': 'base64', 'content': base64.b64encode(content.encode()).decode()}
        return httpx.Response(200, json=data)
    client = GitHubClient(transport=httpx.MockTransport(handler))
    snapshot = client.snapshot('https://github.com/alice/demo', ['Python'])
    client.close()
    assert snapshot.commit == SHA and snapshot.files['src/main.py'] == content
    assert snapshot.tree_truncated and snapshot.skipped
    assert all(url.startswith('https://api.github.com/') for url in paths)
    source = next(iter(snapshot.sources.values()))
    assert verified_source(snapshot, source.source_id)
    assert '/blob/' + SHA in source.url


def test_profile_pagination_ranking_no_star_influence():
    pages = []
    def handler(request):
        if request.url.path.endswith('/repos'):
            page = int(request.url.params['page'])
            pages.append(page)
            rows = [{'full_name': f'alice/docs{index}', 'description': 'Documentation', 'language': None, 'topics': [], 'fork': False, 'stargazers_count': 1_000_000} for index in range(20)] if page == 1 else [{'full_name': 'alice/python', 'description': 'Python testing', 'language': 'Python', 'topics': ['testing'], 'fork': False, 'stargazers_count': 0}, {'full_name': 'alice/fork', 'language': 'Python', 'fork': True}]
            return httpx.Response(200, json=rows)
        return httpx.Response(404)
    client = GitHubClient(transport=httpx.MockTransport(handler))
    result = client.scan_profile('https://github.com/alice', ['Python', 'Testing'])
    client.close()
    assert pages == [1, 2]
    assert result.suggested_url == 'https://github.com/alice/python'
    assert not next(o for o in result.repositories if o.url == result.suggested_url).fork


@pytest.mark.parametrize('status,headers', [(404, {}), (429, {}), (403, {'x-ratelimit-remaining': '0'}), (302, {'location': 'https://evil.com'})])
def test_github_errors_and_redirects(status, headers):
    client = GitHubClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, headers=headers)))
    with pytest.raises(GitHubError):
        client.snapshot('https://github.com/alice/demo', ['Python'])
    client.close()


def test_unexpected_endpoint_and_oversized_response_blocked():
    client = GitHubClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 100)))
    with pytest.raises(GitHubError, match='endpoint'):
        client._get('https://evil.com')
    with pytest.raises(GitHubError, match='size'):
        client._get('/repos/alice/demo', max_bytes=10)
    client.close()
