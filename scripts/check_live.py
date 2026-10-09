"""Opt-in read-only integration checks using synthetic inputs."""
import argparse
import os
import re
import time

from prored.github import GitHubClient, GitHubError
from prored.provider import GroqProvider, ProviderError
from prored.schemas import SkillSuggestions
from prored.sources import verified_source
from prored.config import load_config
from prored.service import Service, build_report


def main():
    load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument('--github', action='store_true')
    parser.add_argument('--ai', action='store_true')
    parser.add_argument('--flow', action='store_true', help='Live synthetic end-to-end flow; consumes additional API quota.')
    parser.add_argument('--retry-rate', action='store_true', help='For integration verification only: at most two short waits per rate-limited operation.')
    parser.add_argument('--model', help='Override GROQ_MODEL for this synthetic check process only; does not edit .env.')
    args = parser.parse_args()
    if args.model:
        os.environ['GROQ_MODEL'] = args.model
    failures = 0
    snapshot = None
    def perform(operation):
        for attempt in range(3 if args.retry_rate else 1):
            try:
                return operation()
            except ProviderError as error:
                if not args.retry_rate or 'rate limit' not in str(error).lower() or attempt >= 2:
                    raise
                match = re.search(r'Retry after (\d+) seconds', str(error))
                pause = min(60, max(30, int(match.group(1)) + 2)) if match else 30
                print(f'LIVE FLOW: rate-limited; waiting {pause}s, bounded retry {attempt + 1}/2. Completed steps remain cached.', flush=True)
                time.sleep(pause)
    if args.github:
        client = GitHubClient(os.getenv('GITHUB_TOKEN', ''))
        try:
            snapshot = client.snapshot('https://github.com/pypa/sampleproject', ['Python', 'Testing'])
            assert snapshot.files and snapshot.sources
            assert all(verified_source(snapshot, sid) for sid in snapshot.sources)
            print(f'LIVE GitHub OK: {snapshot.repository}; commit={snapshot.commit}; files={len(snapshot.files)}; snippets={len(snapshot.sources)}; truncated={snapshot.tree_truncated}')
        except (GitHubError, AssertionError) as error:
            print(f'LIVE GitHub FAILED: {error}')
            failures += 1
        finally:
            client.close()
    if args.ai:
        if not os.getenv('GROQ_API_KEY') or not os.getenv('GROQ_MODEL'):
            print('LIVE AI SKIPPED: configure GROQ_API_KEY and GROQ_MODEL; no mock fallback.')
        else:
            client = GroqProvider()
            try:
                result = client.generate('Extract technical skills from this synthetic JD.', {'job_description': 'Python developer with SQL and testing experience.'}, SkillSuggestions)
                assert result.skills
                print(f'LIVE Groq OK: model={client.model}; validated technical skill extraction.')
            except (ProviderError, AssertionError) as error:
                print(f'LIVE Groq FAILED: {error}')
                failures += 1
            finally:
                client.close()
    if args.flow:
        if not snapshot or not os.getenv('GROQ_API_KEY') or not os.getenv('GROQ_MODEL'):
            print('LIVE FLOW SKIPPED: requires --github, credentials and a fetched snapshot.', flush=True)
        else:
            client = GroqProvider()
            try:
                service = Service(client)
                claims = perform(lambda: service.extract_cv('Skills: Python, Testing. Project: sampleproject - a Python packaging demonstration with a hello-world function and tests.'))
                print('LIVE FLOW: CV extraction validated.', flush=True)
                skills = ['Python', 'Testing']
                comparison = perform(lambda: service.compare(snapshot, skills, claims.skills, 'sampleproject | Python packaging demonstration with tests'))
                print('LIVE FLOW: comparison and source references validated.', flush=True)
                assessment = perform(lambda: service.plan(snapshot, skills, comparison))
                print('LIVE FLOW: two questions and one coding task with stored rubrics validated.', flush=True)
                while assessment.current:
                    current = assessment.current
                    answer = current.item.starter_code + '\n# Synthetic incomplete submission; no code was executed.' if current.item.kind == 'coding' else 'The snippet demonstrates Python behavior. Edge cases include empty inputs and invalid types. I would validate with targeted tests; those tests have not been run. This synthetic answer may be incomplete.'
                    perform(lambda: service.submit(assessment, snapshot, current.item_id, answer))
                    print(f'LIVE FLOW: {current.item_id} reviewed; difficulty={current.item.difficulty}; follow-ups bounded.', flush=True)
                report = build_report(skills, claims.skills, None, snapshot, comparison, assessment)
                assert report['complete'] and len(assessment.attempts) == 6
                print('LIVE FLOW OK: three dimensions, six reviewed attempts, no code execution or persisted CV.', flush=True)
            except (ProviderError, AssertionError) as error:
                print(f'LIVE FLOW FAILED: {error}', flush=True)
                failures += 1
            finally:
                client.close()
    return failures


if __name__ == '__main__':
    raise SystemExit(main())
