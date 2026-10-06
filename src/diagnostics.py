from typing import Literal

import msgspec

"""
Custom error reporting for invalid parC YAML files.
"""

Stage = Literal["decode", "dependencies", "compile"]


class Location(msgspec.Struct, frozen=True, kw_only=True):
    file: str | None = None
    struct: str | None = None
    field: str | None = None
    span: tuple[int, int] | None = None


class Diagnostic(msgspec.Struct, frozen=True, kw_only=True):
    message: str
    stage: Stage
    location: Location
    related: tuple[Location, ...]


class DiagnosticError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


def build_diagnostic_error(
    message: str,
    stage: Stage | None = None,
    file: str | None = None,
    struct: str | None = None,
    field: str | None = None,
    span: tuple[int, int] | None = None,
    related: tuple[Location, ...] | None = None,
    existing: DiagnosticError | None = None,
) -> DiagnosticError:
    location = Location(
        file=file or getattr(existing, "file", None),
        struct=struct or getattr(existing, "struct", None),
        field=field or getattr(existing, "field", None),
        span=span or getattr(existing, "span", None),
    )
    diagnostic = Diagnostic(
        message=message or getattr(existing, "message", None),
        stage=stage or getattr(existing, "stage", None),
        location=location or getattr(existing, "location", None),
        related=related or getattr(existing, "related", None),
    )
    return DiagnosticError(diagnostic)
