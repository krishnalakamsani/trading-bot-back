from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class ClosedCandleContext:
    current_candle_time: datetime
    candle_interval_seconds: int
    close: float
    enforce_recent_exit_cooldown: bool = True
    mds_snapshot: Optional[dict] = None
    signal: Optional[str] = None
    flipped: bool = False
    index_ltp: float = 0.0


class StrategyRuntime:
    def _recent_exit_cooldown_active(self, bot: Any, current_candle_time: datetime, candle_interval_seconds: int) -> bool:
        if not getattr(bot, 'last_exit_candle_time', None):
            return False
        elapsed = (current_candle_time - bot.last_exit_candle_time).total_seconds()
        return elapsed < candle_interval_seconds

    async def on_closed_candle(self, bot: Any, ctx: ClosedCandleContext) -> bool:
        """Default behavior - no action. Return True if an exit was executed."""
        return False


class ScoreMdsRuntime(StrategyRuntime):
    async def on_closed_candle(self, bot: Any, ctx: ClosedCandleContext) -> bool:
        if ctx.mds_snapshot is None:
            return False

        if bool(ctx.enforce_recent_exit_cooldown) and self._recent_exit_cooldown_active(
            bot,
            current_candle_time=ctx.current_candle_time,
            candle_interval_seconds=ctx.candle_interval_seconds,
        ):
            return False

        try:
            exited = await bot.process_mds_on_close(ctx.mds_snapshot, float(ctx.close))
            if exited:
                # Also set last_exit_candle_time for safety
                bot.last_exit_candle_time = ctx.current_candle_time
            return bool(exited)
        except Exception:
            return False


def build_strategy_runtime(indicator_type: Optional[str]) -> StrategyRuntime:
    # Strategy runtime factory - only ScoreMdsRuntime is supported now
    return ScoreMdsRuntime()
