"""Compatibility entry point for source retrieval logic; production orchestration is in build_data.py."""
from towersignal.fetch import fetch_dataset, fetch_metadata, fetch_where

__all__ = ["fetch_dataset", "fetch_metadata", "fetch_where"]
