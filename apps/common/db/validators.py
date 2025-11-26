from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


@deconstructible
class NoWhitespaceValidator:
    message = _("Leading and trailing whitespaces are not allowed.")
    code = "no_whitespace"

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        whitelist: list[str] | None = None,
    ):
        self.message = message or self.message
        self.code = code or self.code

    def __call__(self, value: str) -> None:
        value = force_str(value)

        if value != value.strip():
            params = {"value": value}
            raise ValidationError(self.message, code=self.code, params=params)

    def __eq__(self, other):
        return (
            isinstance(other, NoWhitespaceValidator)
            and (self.message == other.message)
            and (self.code == other.code)
        )
