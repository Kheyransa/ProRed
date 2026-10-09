from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from prored.intake import IntakeError, extract_github_links, extract_pdf_text, normalize_skills, validate_github_url


def sample_pdf(text=None, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(content)
    if encrypted:
        writer.encrypt('secret')
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_text_and_links():
    text = extract_pdf_text(sample_pdf('Python https://github.com/alice/demo'))
    assert 'Python' in text
    assert extract_github_links(text) == ['https://github.com/alice/demo']


@pytest.mark.parametrize('data,message', [(b'bad', 'not a PDF'), (b'%PDF-broken', 'Could not extract'), (sample_pdf(), 'Scanned'), (sample_pdf('Hello', True), 'Password-protected'), (b'x' * (10 * 1024 * 1024 + 1), '10 MB')], ids=['not-pdf', 'corrupt', 'scanned', 'encrypted', 'oversized'])
def test_pdf_errors(data, message):
    with pytest.raises(IntakeError, match=message):
        extract_pdf_text(data)


@pytest.mark.parametrize('value', ['https://evil.com/a', 'https://github.com.evil.com/a', 'https://user@github.com/a', 'https://github.com/a/b/tree/main', 'https://github.com/a?x=1', 'http://github.com/a', 'https://github.com/a%2Fb', 'https://github.com/settings', 'https://github.com/a/..', 'https://github.com:443/a'])
def test_reject_unsafe_or_unsupported_urls(value):
    with pytest.raises(IntakeError):
        validate_github_url(value)


def test_url_normalization_and_link_deduplication():
    assert validate_github_url(' github.com/alice/demo.git/ ').url == 'https://github.com/alice/demo'
    assert validate_github_url('https://github.com/alice').kind == 'Profile'
    assert extract_github_links('(https://github.com/alice/demo), github.com/alice/demo. https://github.com/alice/other') == ['https://github.com/alice/demo', 'https://github.com/alice/other']


def test_skills_have_no_two_skill_limit():
    assert normalize_skills(['Python', ' python ', 'SQL', 'Git', '', 'Testing']) == ['Python', 'SQL', 'Git', 'Testing']
