"""Local intake helpers. No network requests or submitted-code execution."""

from dataclasses import dataclass
from io import BytesIO
import re
from urllib.parse import urlsplit

from pypdf import PdfReader

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_TEXT_CHARS = 100_000


class IntakeError(ValueError):
    """An actionable intake validation error."""


@dataclass(frozen=True)
class GitHubTarget:
    url: str
    owner: str
    repository: str | None = None

    @property
    def kind(self) -> str:
        return "Repository" if self.repository else "Profile"


def validate_github_url(value: str) -> GitHubTarget:
    value = value.strip()
    if value.lower().startswith(("github.com/", "www.github.com/")):
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise IntakeError("Enter a valid GitHub profile or repository URL.") from error
    if (parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}
            or parsed.username or parsed.password or port is not None
            or parsed.query or parsed.fragment):
        raise IntakeError("Use an HTTPS github.com profile or repository URL without query parameters or fragments.")
    parts = parsed.path.strip("/").split("/")
    if len(parts) not in {1, 2} or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", parts[0]):
        raise IntakeError("Use github.com/username or github.com/username/repository.")
    if parts[0].lower() in {"settings", "login", "signup", "explore", "topics", "orgs", "users", "search", "marketplace", "features", "about", "contact", "pricing", "notifications", "new"}:
        raise IntakeError("This is a GitHub navigation page, not a profile or repository.")
    repo = parts[1] if len(parts) == 2 else None
    if repo:
        repo = repo.removesuffix(".git")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in {".", ".."}:
            raise IntakeError("The repository name is invalid.")
    elif len(parts) == 2:
        raise IntakeError("The repository name is missing.")
    return GitHubTarget("https://github.com/" + parts[0] + ("/" + repo if repo else ""), parts[0], repo)


def extract_github_links(text: str) -> list[str]:
    links = []
    for match in re.finditer(r"(?i)(?:https?://)?(?:www\.)?github\.com/[^\s<>\"\[\](){}]+", text):
        raw = match.group().rstrip(".,;:!?")
        try:
            target = validate_github_url(raw)
        except IntakeError:
            continue
        if target.url not in links:
            links.append(target.url)
    return links


def normalize_skills(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        skill = value.strip()
        if skill and skill.casefold() not in seen:
            result.append(skill)
            seen.add(skill.casefold())
    return result


def extract_pdf_text(data: bytes) -> str:
    if not data or len(data) > MAX_PDF_BYTES:
        raise IntakeError("Upload a non-empty PDF no larger than 10 MB.")
    if not data.lstrip().startswith(b"%PDF-"):
        raise IntakeError("The uploaded file is not a PDF.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise IntakeError("Password-protected PDFs are unsupported. Upload an unlocked copy.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise IntakeError("Upload a CV with at most 30 pages.")
        chunks = []
        total = 0
        for page in reader.pages:
            chunk = page.extract_text() or ""
            total += len(chunk)
            if total > MAX_TEXT_CHARS:
                raise IntakeError("The PDF contains too much text; upload a shorter CV.")
            chunks.append(chunk)
        text = "\n\n".join(chunks).strip()
    except IntakeError:
        raise
    except Exception as error:
        raise IntakeError("Could not extract this PDF. Upload a valid text-based PDF.") from error
    if not text:
        raise IntakeError("No readable text found. Scanned/image-only PDFs are unsupported; OCR is not available.")
    return text
