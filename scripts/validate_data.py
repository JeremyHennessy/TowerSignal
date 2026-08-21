"""Compatibility entry point for data-quality gates."""
from towersignal.validate import DataValidationError, validate_generated, validate_normalized, validate_sources

__all__ = ["DataValidationError", "validate_generated", "validate_normalized", "validate_sources"]
