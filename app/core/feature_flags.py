"""Feature-flag helpers for mobile-first runtime simplification."""

from fastapi import HTTPException, status


HEAVY_EXPORT_DISABLED_MESSAGE = "Ekspor berat sedang dinonaktifkan selama mode ujian/puncak."


def feature_disabled_exception(
    feature_name: str,
    *,
    status_code: int = status.HTTP_404_NOT_FOUND,
    message: str | None = None,
) -> HTTPException:
    """Build a consistent HTTPException for disabled optional/legacy features."""
    safe_message = message
    if not safe_message and feature_name == "heavy_export":
        safe_message = HEAVY_EXPORT_DISABLED_MESSAGE

    return HTTPException(
        status_code=status_code,
        detail={
            "error": "FEATURE_DISABLED",
            "feature": feature_name,
            "message": safe_message or f"Fitur {feature_name} sedang dinonaktifkan.",
        },
    )


def require_feature_enabled(
    enabled: bool,
    feature_name: str,
    *,
    status_code: int = status.HTTP_404_NOT_FOUND,
    message: str | None = None,
) -> None:
    """Raise a safe disabled-feature response when a feature flag is off."""
    if not enabled:
        raise feature_disabled_exception(
            feature_name,
            status_code=status_code,
            message=message,
        )
