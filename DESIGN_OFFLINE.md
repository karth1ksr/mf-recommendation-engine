# Offline Batch Processing Design

## Overview
The offline batch pipeline is responsible for maintaining the data foundation of the Mutual Fund Recommendation Engine. It processes raw data from external sources (AMFI, CSV logs, TER reports) and transforms it into a "golden dataset" of normalized metrics that the online engine can query with sub-millisecond latency.

## Architecture & Components

### 1. Fund Master Pipeline (`FundMasterPipeline`)
*   **Source**: `data/scheme_details.csv`
*   **Responsibility**: 
    *   Ingests all mutual fund schemes into `fund_master` collection.
    *   Normalizes names and identifies categories (Equity, Debt, Hybrid).
    *   Flags "eligible" funds based on data availability and scheme age.

### 2. NAV Ingestion Pipeline (`NavPipeline`)
*   **Source**: AMFI Daily NAV API / Archives.
*   **Responsibility**: 
    *   **Incremental Sync**: Fetches the latest daily NAV for all funds.
    *   **Historical Sync**: Backfills 3-5 years of historical data for new funds.
    *   **Storage**: `nav_timeseries` (MongoDB Time Series collection).

### 3. TER Pipeline (`TerPipeline`)
*   **Source**: `data/ter_data.xlsx` (Monthly reports).
*   **Responsibility**:
    *   Parses Total Expense Ratio (TER) data.
    *   Maps AMFI codes to internal `fund_id`.
    *   Stores snapshots in `ter_snapshot`.

### 4. Metrics Computation Pipeline (`MetricsPipeline`)
*   **Objective**: Convert time-series NAV into actionable performance indicators.
*   **Computation Steps**:
    1.  **CAGR**: 3-year and 5-year annualized returns.
    2.  **Risk**: Standard Deviation (Volatility) and Sharpe Ratio.
    3.  **Consistency**: 3-year rolling returns consistency (how often the fund beat its category average).
    4.  **Cost**: Latest Expense Ratio.
*   **Optimization**: Uses `ProcessPoolExecutor` for parallel CPU-bound computation across thousands of funds.
*   **Normalization**: Applies **Z-Score Normalization** per category (e.g., comparing a Small Cap fund only against other Small Cap funds).

---

## Workflow Sequence

1.  **Ingest Master**: Update list of schemes and check eligibility.
2.  **Fetch Data**: Pull latest NAV and TER values.
3.  **Compute Raw Metrics**: Run heavy math on historical prices.
4.  **Normalize**: Transform metrics into a 0-1 relative score.
5.  **Persist**: Store final results in `fund_metrics` for the Online Engine.

---

## Technical Stack
- **Database**: MongoDB (Timeseries & Standard collections).
- **Processing**: Pandas, NumPy (Vectorized operations).
- **Concurrency**: Multiprocessing for speed.
