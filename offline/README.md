# Metric Based Mutual Fund Recommendation (Offline)

This folder contains the offline processing components for the mutual fund recommendation system.

## Structure

- **config/**: Configuration settings and logging setup.
- **ingestion/**: Scripts for ingesting NAV, fund master data, and TER.
- **validation/**: Data validation and normalization logic.
- **metrics/**: Calculation of various metrics (performance, risk, stability, cost).
- **storage/**: Database interaction layers (repositories).
- **pipelines/**: Orchestration of data pipelines.
- **utils/**: Utility functions for date, math, and text processing.
- **main.py**: Entry point for the offline system.
