"""Bounded GitHub REST reads, with no user-controlled host or redirects."""
import base64
from dataclasses import dataclass
import re
from urllib.parse import quote

import httpx

from prored.intake import validate_github_url
from prored.sources import DEPENDENCIES, Snapshot, build_sources

MAX_PROFILE_REPOS = 40
PROFILE_PAGE_SIZE = 20
MAX_DEPENDENCY_PROBES = 6
MAX_FILES = 12
MAX_FILE_BYTES = 40_000
MAX_TOTAL_BYTES = 120_000
MAX_TREE_BYTES = 8_000_000
EXCLUDED = {".git", ".venv", "venv", "node_modules", "vendor", "dist", "build", "__pycache__"}


class GitHubError(ValueError):
    pass


@dataclass
class RepositoryOption:
    url: str
    description: str
    language: str
    topics: list[str]
    fork: bool
    relevance: int = 0
    explanation: str = ""


@dataclass
class ProfileScan:
    repositories: list[RepositoryOption]
    suggested_url: str | None
    limitations: list[str]


class GitHubClient:
    def __init__(self, token: str = "", transport=None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(base_url="https://api.github.com", headers=headers, timeout=20, follow_redirects=False, transport=transport)

    def close(self):
        self.client.close()

    def _get(self, path: str, params=None, max_bytes=MAX_TREE_BYTES):
        if not re.fullmatch(r"/(?:users/[A-Za-z0-9-]+/repos|repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+(?:/(?:commits/[^/]+|git/trees/[0-9a-f]{40}|git/blobs/[0-9a-f]{40}|contents/[^?#]+))?)", path):
            raise GitHubError("Unexpected GitHub endpoint blocked.")
        try:
            with self.client.stream("GET", path, params=params) as response:
                if response.status_code in {403, 429}:
                    if response.status_code == 429 or response.headers.get("x-ratelimit-remaining") == "0" or response.headers.get("retry-after"):
                        raise GitHubError("GitHub rate limit reached. Wait before retrying or configure GITHUB_TOKEN.")
                    raise GitHubError("GitHub denied access. Check repository visibility or token permissions.")
                if response.status_code == 404:
                    raise GitHubError("GitHub resource is unavailable, private, or does not exist.")
                if response.is_redirect:
                    raise GitHubError("GitHub redirected this resource. Use its current canonical URL.")
                if response.status_code >= 400:
                    raise GitHubError(f"GitHub request failed (HTTP {response.status_code}).")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise GitHubError("GitHub response exceeded the configured size limit.")
                import json
                result = json.loads(data)
                if not isinstance(result, (dict, list)):
                    raise GitHubError("GitHub returned an invalid response shape.")
                return result
        except GitHubError:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise GitHubError("GitHub timed out, could not be reached, or returned invalid data.") from error

    def _repo_path(self, url: str) -> str:
        target = validate_github_url(url)
        if not target.repository:
            raise GitHubError("Select a repository first.")
        return f"/repos/{target.owner}/{target.repository}"

    def _dependency_probe(self, url: str) -> str:
        root = self._repo_path(url)
        # Profile ranking uses current metadata only; the final inspection is pinned separately.
        for name in ("pyproject.toml", "requirements.txt"):
            try:
                result = self._get(root + "/contents/" + name, max_bytes=80_000)
                if result.get("size", MAX_FILE_BYTES + 1) <= MAX_FILE_BYTES and result.get("encoding") == "base64":
                    return base64.b64decode(result["content"]).decode("utf-8")[:MAX_FILE_BYTES]
            except GitHubError as error:
                if "rate limit" in str(error).lower():
                    raise
            except (ValueError, KeyError, UnicodeError):
                continue
        return ""

    def scan_profile(self, url: str, skills: list[str]) -> ProfileScan:
        target = validate_github_url(url)
        if target.repository:
            raise GitHubError("A profile URL is required for profile scanning.")
        options = []
        limitations = [f"Scanned at most {MAX_PROFILE_REPOS} public repositories; dependency probes cover at most {MAX_DEPENDENCY_PROBES} relevant non-forks."]
        for page in range(1, MAX_PROFILE_REPOS // PROFILE_PAGE_SIZE + 1):
            rows = self._get(f"/users/{target.owner}/repos", {"per_page": PROFILE_PAGE_SIZE, "page": page, "sort": "updated", "type": "owner"})
            if not isinstance(rows, list):
                raise GitHubError("GitHub returned an invalid repository list.")
            for row in rows:
                try:
                    repo_url = validate_github_url("https://github.com/" + row["full_name"]).url
                    option = RepositoryOption(repo_url, row.get("description") or "", row.get("language") or "Unknown", row.get("topics") or [], bool(row.get("fork")))
                    text = " ".join([option.description, option.language] + option.topics).lower()
                    matched = [skill for skill in skills if skill.lower() in text]
                    option.relevance = 3 * len(matched) + (1 if option.language == "Python" else 0)
                    option.explanation = "Metadata relevance: " + (", ".join(matched) or "no selected-skill keyword match")
                    options.append(option)
                except (KeyError, ValueError, TypeError):
                    continue
            if len(rows) < PROFILE_PAGE_SIZE:
                break
        eligible = sorted((o for o in options if not o.fork), key=lambda o: (-o.relevance, o.url))
        for option in eligible[:MAX_DEPENDENCY_PROBES]:
            try:
                dependencies = self._dependency_probe(option.url).lower()
                matches = [skill for skill in skills if skill.lower() in dependencies]
                option.relevance += 2 * len(matches)
                if matches:
                    option.explanation += "; dependency keywords: " + ", ".join(matches) + " (declarations only)"
            except GitHubError as error:
                limitations.append(str(error))
                break
        options.sort(key=lambda o: (o.fork, -o.relevance, o.url))
        eligible = [o for o in options if not o.fork]
        suggested = eligible[0].url if eligible else None
        if not suggested:
            limitations.append("No non-fork repository found in the bounded list. Enter a direct repository URL instead.")
        return ProfileScan(options, suggested, limitations)

    def snapshot(self, url: str, skills: list[str]) -> Snapshot:
        root = self._repo_path(url)
        metadata = self._get(root)
        if not isinstance(metadata, dict):
            raise GitHubError("GitHub returned invalid repository metadata.")
        if metadata.get("private"):
            raise GitHubError("Only public repositories are supported.")
        branch = metadata.get("default_branch")
        if not branch:
            raise GitHubError("Repository has no default branch.")
        commit = self._get(root + "/commits/" + quote(branch, safe=""))
        if not isinstance(commit, dict):
            raise GitHubError("GitHub returned invalid commit metadata.")
        sha = commit.get("sha", "")
        tree_sha = commit.get("commit", {}).get("tree", {}).get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
            raise GitHubError("Repository has no usable commit/tree.")
        tree = self._get(root + "/git/trees/" + tree_sha, {"recursive": "1"})
        if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
            raise GitHubError("GitHub returned an invalid file tree.")
        candidates = []
        skipped = []
        for item in tree.get("tree", []):
            path = item.get("path", "")
            name = path.rsplit("/", 1)[-1].lower()
            if item.get("type") != "blob" or any(part in EXCLUDED for part in path.split("/")):
                continue
            if not (path.endswith(".py") or name.startswith("readme") or name in DEPENDENCIES or name.startswith("requirements")):
                continue
            if any(part in {"", ".", ".."} for part in path.split("/")) or item.get("mode") == "120000":
                skipped.append(path + ": invalid path or symlink")
                continue
            size = item.get("size", MAX_FILE_BYTES + 1)
            if not 0 < size <= MAX_FILE_BYTES:
                skipped.append(path + ": empty or larger than file limit")
                continue
            priority = 0 if name.startswith("readme") else 1 if name in DEPENDENCIES or name.startswith("requirements") else 2
            relevance = sum(skill.lower().replace(" ", "_") in path.lower() for skill in skills)
            candidates.append((priority, -relevance, path, item))
        candidates.sort(key=lambda row: (row[0], row[1], len(row[2]), row[2]))
        files = {}
        total = 0
        # Reserve a test slot when tests exist, rather than allowing only short source paths.
        chosen = candidates[:MAX_FILES]
        test_rows = [r for r in candidates if "test" in r[2].lower() and r[2].endswith(".py")]
        if test_rows and chosen and not any("test" in r[2].lower() for r in chosen):
            chosen[-1] = test_rows[0]
        for _, _, path, item in chosen:
            if total + item["size"] > MAX_TOTAL_BYTES:
                skipped.append(path + ": total content limit")
                continue
            blob_sha = item.get("sha", "")
            if not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
                skipped.append(path + ": invalid blob ID")
                continue
            try:
                blob = self._get(root + "/git/blobs/" + blob_sha, max_bytes=80_000)
                if blob.get("encoding") != "base64":
                    raise ValueError("Unsupported encoding")
                raw = base64.b64decode(blob["content"])
                if len(raw) > MAX_FILE_BYTES or total + len(raw) > MAX_TOTAL_BYTES or b"\0" in raw:
                    skipped.append(path + ": binary or size limit")
                    continue
                content = raw.decode("utf-8")
                if not content.strip():
                    skipped.append(path + ": empty text")
                    continue
                files[path] = content
                total += len(raw)
            except GitHubError as error:
                if "rate limit" in str(error).lower():
                    raise
                skipped.append(path + ": " + str(error))
            except (ValueError, KeyError, UnicodeError):
                skipped.append(path + ": unreadable UTF-8 text")
        selected_paths = {row[2] for row in chosen}
        skipped += [row[2] + ": file count limit" for row in candidates if row[2] not in selected_paths]
        snapshot = Snapshot(validate_github_url(url).url, sha, files, skipped, bool(tree.get("truncated")), len(candidates), False)
        build_sources(snapshot)
        return snapshot
