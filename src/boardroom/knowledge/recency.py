from __future__ import annotations

import math
from datetime import datetime, timezone

from boardroom.knowledge.models import KnowledgeItem

_SIX_MONTHS_DAYS = 180


class RecencyScorer:
    """Score items by freshness. Items within 6 months get high scores; decay after that."""

    def score(self, item: KnowledgeItem) -> float:
        now = datetime.now(timezone.utc)
        ts = item.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - ts).days)
        if age_days <= _SIX_MONTHS_DAYS:
            return 1.0 - (age_days / _SIX_MONTHS_DAYS) * 0.3
        decay = math.exp(-0.005 * (age_days - _SIX_MONTHS_DAYS))
        return max(0.1, 0.7 * decay)
