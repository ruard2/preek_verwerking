"""Tekst uit een geüpload preekdocument halen (PDF, DOCX, TXT).

Zo kan een predikant zijn eigen preek aanleveren i.p.v. via YouTube/Kerkdienst-
gemist. De tekst gaat daarna door dezelfde AI-verwerking als een transcript.
"""

import io


def haal_tekst(bestandsnaam, inhoud: bytes):
    """Geef de platte tekst van het document terug. Werpt een nette fout."""
    naam = (bestandsnaam or "").lower()
    if naam.endswith(".txt"):
        return inhoud.decode("utf-8", "replace").strip()
    if naam.endswith(".pdf"):
        return _uit_pdf(inhoud)
    if naam.endswith(".docx"):
        return _uit_docx(inhoud)
    if naam.endswith(".doc"):
        raise ValueError(
            "Het oude .doc-formaat wordt niet ondersteund. Sla het op als .docx of .pdf."
        )
    raise ValueError("Onbekend bestandstype. Gebruik PDF, DOCX of TXT.")


def _uit_pdf(inhoud):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(inhoud))
    tekst = "\n".join((p.extract_text() or "") for p in reader.pages)
    if not tekst.strip():
        raise ValueError(
            "Uit deze PDF kon geen tekst worden gehaald (mogelijk een scan zonder "
            "OCR). Lever een tekst-PDF of DOCX aan."
        )
    return tekst.strip()


def _uit_docx(inhoud):
    import docx  # python-docx

    document = docx.Document(io.BytesIO(inhoud))
    tekst = "\n".join(p.text for p in document.paragraphs)
    if not tekst.strip():
        raise ValueError("Dit document lijkt leeg te zijn.")
    return tekst.strip()
