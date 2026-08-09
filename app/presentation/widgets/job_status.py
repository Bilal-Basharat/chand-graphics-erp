"""
How far a job order has got.

Shared for the same reason `payment_status.py` is: the job list, the
dashboard and the printed job card all name the same five states, and a
job that reads "In production" on one and "Started" on another reads as
two different jobs.

The tone is a name, not a colour — the card model and the screen both
take it from here, and paper does not use the screen's palette.
"""
from __future__ import annotations

from app.domain.enums.job_status import JobStatus
from app.presentation.records.card import TONE_COLORS, Tone

_WORDS: dict[JobStatus, str] = {
    JobStatus.DRAFT: "Draft",
    JobStatus.IN_PRODUCTION: "In production",
    JobStatus.COMPLETED: "Completed",
    JobStatus.DELIVERED: "Delivered",
    JobStatus.CANCELLED: "Cancelled",
}

_TONES: dict[JobStatus, Tone] = {
    JobStatus.DRAFT: "muted",
    JobStatus.IN_PRODUCTION: "warning",
    JobStatus.COMPLETED: "info",
    JobStatus.DELIVERED: "success",
    JobStatus.CANCELLED: "danger",
}


def job_status(job) -> JobStatus:
    # Qt round-trips enums through QVariant as plain strings in places, and
    # the ORM hands back whatever the column held.
    return JobStatus(job.status)


def job_status_text(job) -> str:
    return _WORDS.get(job_status(job), str(job.status))


def job_status_tone(job) -> Tone:
    return _TONES.get(job_status(job), "muted")


def job_status_color(job) -> str:
    """The tone above as the screen paints it, for a table column."""
    return TONE_COLORS[job_status_tone(job)]
