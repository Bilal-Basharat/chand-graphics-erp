from __future__ import annotations

SHARED_FIELDS = (
    "id",
    "created_at",
    "updated_at",
    "created_by_user_id",
    "updated_by_user_id",
)


def copy_shared_fields(source: object, target: object) -> None:
    """
    Copy common identity and audit fields between domain entities and ORM models.

    This keeps mapping explicit and avoids reflection-heavy magic.
    Missing attributes are ignored safely.
    """
    for field_name in SHARED_FIELDS:
        if hasattr(source, field_name) and hasattr(target, field_name):
            setattr(target, field_name, getattr(source, field_name))