"""Create a synthetic text-based CV fixture; no candidate data."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

root = Path(__file__).resolve().parent.parent
writer = PdfWriter()
page = writer.add_blank_page(width=612, height=792)
font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
lines = (root / 'examples' / 'sample_cv.txt').read_text(encoding='utf-8').splitlines()
stream = DecodedStreamObject()
stream.set_data(('BT /F1 11 Tf 48 730 Td 22 TL ' + ' '.join('(' + line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ') Tj T*' for line in lines) + ' ET').encode('ascii'))
page[NameObject('/Contents')] = writer._add_object(stream)
with (root / 'examples' / 'sample_cv.pdf').open('wb') as output:
    writer.write(output)
