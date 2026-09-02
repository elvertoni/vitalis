"""Shared field validators."""

import uuid
from pathlib import Path

from django.core.exceptions import ValidationError

ALLOWED_ATTACHMENT_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
MAX_ATTACHMENT_SIZE_MB = 10


def validate_attachment(value):
    """
    Accepts only PDF and common image formats, up to ten megabytes.
    Validates both the extension and the binary magic bytes of the file.
    """
    extension = Path(value.name).suffix.lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            'Formato não aceito. Envie um arquivo PDF, JPG ou PNG.',
            code='invalid_extension',
        )
    if value.size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
        raise ValidationError(
            f'Arquivo muito grande. O limite é de {MAX_ATTACHMENT_SIZE_MB} MB.',
            code='file_too_large',
        )

    # Validação de integridade do conteúdo via cabeçalho binário (magic bytes)
    try:
        initial_pos = value.tell() if hasattr(value, 'tell') else 0
        header = value.read(8)
        if hasattr(value, 'seek'):
            value.seek(initial_pos)
    except Exception:
        header = b''

    valid = False
    if extension == '.pdf' and header.startswith(b'%PDF-'):
        valid = True
    elif extension in ('.jpg', '.jpeg') and header.startswith(b'\xff\xd8\xff'):
        valid = True
    elif extension == '.png' and header.startswith(b'\x89PNG'):
        valid = True

    if not valid:
        raise ValidationError(
            'O conteúdo do arquivo não corresponde a um documento PDF, JPG ou PNG válido.',
            code='invalid_content',
        )


def attachment_upload_path(instance, filename):
    """
    Builds an unguessable path for uploaded reports.

    The original file name is discarded on purpose: it often carries the patient name or
    the exam type, and the stored path should not leak either. Access still goes through
    an authenticated view; the random name is the second lock, not the first.
    """
    extension = Path(filename).suffix.lower()
    return f'exams/{instance.user_id}/{uuid.uuid4().hex}{extension}'
