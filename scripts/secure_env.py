"""Move configured example credentials to ignored local .env."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
example = root / '.env.example'
local = root / '.env'
template = '''# Server-side configuration. .env is ignored by Git.
# mock needs no credentials; real defaults to Groq and live GitHub.
PRORED_MODE=mock
GROQ_API_KEY=
# Recommended model is checked against Groq's live models endpoint.
GROQ_MODEL=openai/gpt-oss-120b
GITHUB_TOKEN=
'''
text = example.read_text(encoding='utf-8')
configured = [line for line in text.splitlines() if '=' in line and not line.lstrip().startswith('#') and line.split('=', 1)[1].strip()]
if configured:
    existing = local.read_text(encoding='utf-8') if local.exists() else ''
    existing_names = {line.split('=', 1)[0].strip() for line in existing.splitlines() if '=' in line and not line.lstrip().startswith('#')}
    additions = [line for line in configured if line.split('=', 1)[0].strip() not in existing_names]
    if additions:
        local.write_text(existing.rstrip() + '\n' + '\n'.join(additions) + '\n', encoding='utf-8')
example.write_text(template, encoding='utf-8')
print('Local .env preserved; .env.example now contains placeholders only.')
