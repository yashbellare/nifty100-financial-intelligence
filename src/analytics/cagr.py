"""CAGR engine with explicit financial-data edge cases."""
from __future__ import annotations
import math

def cagr(start, end, years):
    if years is None or years <= 0: return None, "INSUFFICIENT"
    if start is None or end is None: return None, "INSUFFICIENT"
    if start == 0: return None, "ZERO_BASE"
    if start > 0 and end > 0:
        return ((end / start) ** (1 / years) - 1) * 100, None
    if start > 0 and end < 0: return None, "DECLINE_TO_LOSS"
    if start < 0 and end > 0: return None, "TURNAROUND"
    if start < 0 and end < 0: return None, "BOTH_NEGATIVE"
    if end == 0:
        # A positive-to-zero path is not a valid multiplicative CAGR.
        return None, "DECLINE_TO_LOSS" if start > 0 else "BOTH_NEGATIVE"
    return None, "INSUFFICIENT"

def cagr_from_series(series, years):
    """Return CAGR using latest observation and the closest observation at least N years earlier."""
    if series is None or len(series) == 0:
        return None, "INSUFFICIENT"
    s = [(int(y), v) for y, v in series if y is not None and v is not None]
    s.sort()
    if len(s) < 2:
        return None, "INSUFFICIENT"
    end_year, end = s[-1]
    candidates = [(y,v) for y,v in s[:-1] if end_year-y >= years]
    if not candidates:
        return None, "INSUFFICIENT"
    start_year, start = max(candidates, key=lambda x: x[0])
    return cagr(start, end, end_year-start_year)
