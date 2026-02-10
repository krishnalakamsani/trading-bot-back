from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str = ""


@dataclass(frozen=True)
class EntryDecision:
    should_enter: bool
    option_type: str = ""  # 'CE' | 'PE'
    reason: str = ""


def decide_exit_mds(*, position_type: str, score: float, slope: float, slow_mom: float) -> ExitDecision:
    """Deterministic exits for the ScoreEngine strategy.

    Mirrors the existing rules in `TradingBot._handle_mds_signal`.
    """
    neutral = abs(score) <= 6.0

    should_exit = False
    reason = ""

    if position_type == "CE":
        if score <= -10.0:
            if slow_mom <= -1.0:
                should_exit = True
                reason = "MDS Reversal (slow confirm)"
        elif neutral:
            if abs(slow_mom) <= 1.0:
                should_exit = True
                reason = "MDS Neutral (slow confirm)"
        elif slope <= -2.0 and score < 12.0:
            if slow_mom <= 0.0:
                should_exit = True
                reason = "MDS Momentum Loss (slow confirm)"

    elif position_type == "PE":
        if score >= 10.0:
            if slow_mom >= 1.0:
                should_exit = True
                reason = "MDS Reversal (slow confirm)"
        elif neutral:
            if abs(slow_mom) <= 1.0:
                should_exit = True
                reason = "MDS Neutral (slow confirm)"
        elif slope >= 2.0 and score > -12.0:
            if slow_mom >= 0.0:
                should_exit = True
                reason = "MDS Momentum Loss (slow confirm)"

    return ExitDecision(should_exit, reason)


def decide_entry_mds(
    *,
    ready: bool,
    is_choppy: bool,
    direction: str,
    score: float,
    slope: float,
    confirm_count: int,
    confirm_needed: int,
) -> EntryDecision:
    if not ready:
        return EntryDecision(False, "", "mds_not_ready")

    if is_choppy:
        return EntryDecision(False, "", "mds_choppy")

    if direction == "NONE":
        return EntryDecision(False, "", "neutral_band")

    if abs(score) < 10.0:
        return EntryDecision(False, "", "score_too_low")

    if abs(slope) < 1.0:
        return EntryDecision(False, "", "slope_too_low")

    if confirm_count < confirm_needed:
        return EntryDecision(False, "", "arming")

    option_type = "CE" if direction == "CE" else "PE"
    return EntryDecision(True, option_type, "")


# --- Runner + Strategy-friendly result classes ---
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyExitDecision:
    should_exit: bool
    reason: str = ""


@dataclass(frozen=True)
class StrategyEntryDecision:
    should_enter: bool
    option_type: str = ""
    reason: str = ""
    confirm_count: int = 0
    confirm_needed: int = 0


class ScoreMdsRunner:
    """Decision-only runner for the MDS/ScoreEngine strategy.

    Owns the multi-candle confirmation state.
    """

    def __init__(self) -> None:
        self._last_direction: Optional[str] = None
        self._confirm_count: int = 0

    def reset(self) -> None:
        self._last_direction = None
        self._confirm_count = 0

    def on_entry_attempted(self) -> None:
        """Call after an entry attempt (success or blocked downstream)."""
        self._confirm_count = 0

    def decide_exit(self, *, position_type: str, score: float, slope: float, slow_mom: float) -> StrategyExitDecision:
        d = decide_exit_mds(
            position_type=str(position_type or ""),
            score=float(score or 0.0),
            slope=float(slope or 0.0),
            slow_mom=float(slow_mom or 0.0),
        )
        return StrategyExitDecision(bool(d.should_exit), str(d.reason or ""))

    def decide_entry(
        self,
        *,
        ready: bool,
        is_choppy: bool,
        direction: str,
        score: float,
        slope: float,
        confirm_needed: int,
    ) -> StrategyEntryDecision:
        direction = str(direction or "NONE")

        if not ready:
            return StrategyEntryDecision(False, "", "mds_not_ready")
        if is_choppy:
            return StrategyEntryDecision(False, "", "mds_choppy")

        if direction == "NONE":
            self._last_direction = direction
            self._confirm_count = 0
            return StrategyEntryDecision(False, "", "neutral_band", confirm_count=0, confirm_needed=confirm_needed)

        if abs(float(score or 0.0)) < 10.0:
            self._last_direction = direction
            self._confirm_count = 0
            return StrategyEntryDecision(False, "", "score_too_low", confirm_count=0, confirm_needed=confirm_needed)

        if abs(float(slope or 0.0)) < 1.0:
            self._last_direction = direction
            self._confirm_count = 0
            return StrategyEntryDecision(False, "", "slope_too_low", confirm_count=0, confirm_needed=confirm_needed)

        if self._last_direction == direction:
            self._confirm_count += 1
        else:
            self._last_direction = direction
            self._confirm_count = 1

        d = decide_entry_mds(
            ready=bool(ready),
            is_choppy=bool(is_choppy),
            direction=direction,
            score=float(score or 0.0),
            slope=float(slope or 0.0),
            confirm_count=int(self._confirm_count),
            confirm_needed=int(confirm_needed or 0),
        )

        return StrategyEntryDecision(
            bool(d.should_enter),
            str(d.option_type or ""),
            str(d.reason or ""),
            confirm_count=int(self._confirm_count),
            confirm_needed=int(confirm_needed or 0),
        )
