"""Compatibility entry point for deterministic signal and priority logic."""
from towersignal.scoring import priority_score
from towersignal.signals import build_signals

__all__ = ["build_signals", "priority_score"]
