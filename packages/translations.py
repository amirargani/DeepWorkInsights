"""Centralized Translation module re-exporting dictionaries from packages.dashboard_data and packages.monitoring_data."""

from packages.dashboard_data import DASHBOARD_TRANSLATIONS
from packages.monitoring_data import MONITORING_TRANSLATIONS

__all__ = ["DASHBOARD_TRANSLATIONS", "MONITORING_TRANSLATIONS"]
