# Data

No manual download needed. `src/fetch_fdic.py` pulls data directly from the **FDIC BankFind Suite API** (`https://api.fdic.gov/banks`), which is free, public, and needs no API key.

- **financials** endpoint: quarterly Call Report metrics for every FDIC-insured bank
- **institutions** endpoint: bank names and locations, including closed banks

Scope: banks with $1B+ in total assets, quarterly since Q1 2020. Change `START_DATE` or `MIN_ASSETS_THOUSANDS` in `src/fetch_fdic.py` to widen it.

Field definitions: see the "Financial API Definitions" file at https://api.fdic.gov/banks/docs/. All dollar amounts from the API are in **thousands**.
