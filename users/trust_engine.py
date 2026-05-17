import logging
from typing import Optional
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import ScoreEvent, EventType, SCORE_DELTAS, TIER_THRESHOLDS, TIER_LEVELS, SCORE_MIN, SCORE_MAX

logger = logging.getLogger('trust_engine')


def calculate_tier(score: float) -> str:
    # Find the correct tier based on the score (e.g., 8.0+ is Elite)
    for threshold, tier_name in TIER_THRESHOLDS:
        if score >= threshold:
            return tier_name
    return 'Suspended'


def clamp_score(score: float) -> float:
    # Keep the score strictly between 0.0 and 10.0
    return round(max(SCORE_MIN, min(SCORE_MAX, score)), 2)


def get_tier_level(tier: str) -> int:
    return TIER_LEVELS.get(tier, 0)


class TrustScoreService:
    @classmethod
    @transaction.atomic
    def apply_event(cls, user, event_type: str, *, days_late: int = 1, custom_delta: Optional[float] = None,
                    reason: str = '', rental_request_id: Optional[int] = None) -> ScoreEvent:
        score_before = user.trust_score
        tier_before = user.trust_tier

        # Calculate new score and tier
        delta = cls._calculate_delta(event_type, days_late, custom_delta)
        score_after = cls._calculate_new_score(event_type, score_before, delta)
        tier_after = calculate_tier(score_after)

        # Update the user's profile
        user.trust_score = score_after
        user.trust_tier = tier_after
        user.save(update_fields=['trust_score', 'trust_tier'])

        # Create a permanent log of this score change
        event = ScoreEvent.objects.create(
            user=user, event_type=event_type, delta=delta,
            score_before=score_before, score_after=score_after,
            tier_before=tier_before, tier_after=tier_after,
            rental_request_id=rental_request_id, reason=reason,
        )
        return event

    @staticmethod
    def _calculate_delta(event_type, days_late, custom_delta) -> float:
        # KYC verification doesn't use a delta, it's a direct jump
        if event_type == EventType.KYC_VERIFIED: return 0.0
        # Admin can manually set any custom penalty/boost
        if event_type == EventType.ADMIN_ADJUSTMENT: return round(float(custom_delta), 2)
        # Multiply penalty by days late
        if event_type == EventType.LATE_RETURN: return round(SCORE_DELTAS[EventType.LATE_RETURN] * max(1, days_late), 2)

        return SCORE_DELTAS.get(event_type, 0.0)

    @staticmethod
    def _calculate_new_score(event_type, score_before, delta) -> float:
        # KYC instantly boosts score to 7.0 (or keeps it higher if they are already Elite)
        if event_type == EventType.KYC_VERIFIED: return clamp_score(max(score_before, 7.0))
        return clamp_score(score_before + delta)