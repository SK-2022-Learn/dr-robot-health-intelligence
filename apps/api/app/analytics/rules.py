"""Versioned non-clinical thresholds for deterministic analytics."""

NUMERIC_CALCULATION_VERSION = "numeric-trend-v1"
FREQUENCY_CALCULATION_VERSION = "symptom-frequency-v1"

DEFAULT_RECENT_WINDOW_DAYS = 30
DEFAULT_BASELINE_WINDOW_DAYS = 90
DEFAULT_STABILITY_THRESHOLD_PERCENT = 5.0
DEFAULT_MIN_RECENT_NUMERIC_POINTS = 2
DEFAULT_MIN_BASELINE_NUMERIC_POINTS = 2

SUPPORTED_WEIGHT_UNITS = {"kg", "kilogram", "kilograms", "lb", "lbs", "pound", "pounds"}
SUPPORTED_DURATION_UNITS = {"min", "minute", "minutes", "h", "hr", "hrs", "hour", "hours"}
