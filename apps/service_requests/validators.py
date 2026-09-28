from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

ALLOWED_ATTACHMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MB

validate_attachment_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS
)


def validate_attachment_size(file):
    if file.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError(
            f"File too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024 * 1024)} MB.",
            code="file_too_large",
        )