"""Exact-content, commit-pinned snippets. Parsing never executes code."""
import ast
import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from prored.intake import validate_github_url

DEPENDENCIES = {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "poetry.lock"}
MAX_SNIPPET_LINES = 45
MAX_SNIPPETS = 48
MAX_SNIPPET_CONTEXT = 24_000


def file_kind(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    if name.startswith("readme"):
        return "README statement"
    if name in DEPENDENCIES or name.startswith("requirements"):
        return "Dependency declaration"
    return "Test implementation" if "test" in path.lower() else "Source implementation"


@dataclass(frozen=True)
class Source:
    source_id: str
    repository: str
    commit: str
    path: str
    start: int
    end: int
    text: str
    kind: str
    mock: bool = False

    @property
    def url(self) -> str | None:
        if self.mock:
            return None
        return f"{self.repository}/blob/{self.commit}/{quote(self.path, safe='/')}#L{self.start}-L{self.end}"

    def payload(self) -> dict:
        return {"source_id": self.source_id, "path": self.path, "kind": self.kind, "text": self.text}


@dataclass
class Snapshot:
    repository: str
    commit: str
    files: dict[str, str]
    skipped: list[str] = field(default_factory=list)
    tree_truncated: bool = False
    candidate_file_count: int = 0
    mock: bool = False
    sources: dict[str, Source] = field(default_factory=dict)

    def __post_init__(self):
        target = validate_github_url(self.repository)
        if not target.repository or not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("A repository and full commit SHA are required.")


def _source_id(repository: str, commit: str, path: str, start: int, end: int, text: str) -> str:
    value = f"{repository}\0{commit}\0{path}\0{start}\0{end}\0{text}"
    return "src_" + hashlib.sha256(value.encode()).hexdigest()[:20]


def build_sources(snapshot: Snapshot) -> dict[str, Source]:
    sources = {}
    context = 0
    for path, content in snapshot.files.items():
        file_context = 0
        file_snippets = 0
        lines = content.splitlines()
        ranges = []
        if path.endswith(".py"):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
                        ranges.append((start, min(node.end_lineno or start, start + MAX_SNIPPET_LINES - 1)))
            except (SyntaxError, ValueError, RecursionError):
                pass
        # Include bounded windows too, for module-level logic and non-Python files.
        ranges += [(start, min(len(lines), start + MAX_SNIPPET_LINES - 1)) for start in range(1, len(lines) + 1, MAX_SNIPPET_LINES)]
        used = set()
        for start, end in ranges:
            if (start, end) in used:
                continue
            used.add((start, end))
            text = "\n".join(lines[start - 1:end])
            if not text.strip() or context + len(text) > MAX_SNIPPET_CONTEXT or len(sources) >= MAX_SNIPPETS or file_context + len(text) > 3000 or file_snippets >= 4:
                continue
            source_id = _source_id(snapshot.repository, snapshot.commit, path, start, end, text)
            sources[source_id] = Source(source_id, snapshot.repository, snapshot.commit, path, start, end, text, file_kind(path), snapshot.mock)
            context += len(text)
            file_context += len(text)
            file_snippets += 1
    snapshot.sources = sources
    return sources


def verified_source(snapshot: Snapshot, source_id: str) -> Source | None:
    source = snapshot.sources.get(source_id)
    if not source or source.repository != snapshot.repository or source.commit != snapshot.commit or source.mock != snapshot.mock:
        return None
    content = snapshot.files.get(source.path)
    if content is None:
        return None
    lines = content.splitlines()
    if not 1 <= source.start <= source.end <= len(lines):
        return None
    text = "\n".join(lines[source.start - 1:source.end])
    if source.text != text or source.source_id != _source_id(snapshot.repository, snapshot.commit, source.path, source.start, source.end, text):
        return None
    return source
