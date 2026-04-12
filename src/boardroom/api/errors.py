from __future__ import annotations


class MeetingCancelledError(RuntimeError):
    """Raised when a running meeting is cancelled by the user."""
