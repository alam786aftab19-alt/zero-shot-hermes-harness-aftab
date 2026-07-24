# Capability: Chart Generation

## What It Does

Transforms a tabular result set into a chart specification (Plotly JSON) suitable for rendering in the frontend. Chooses a default chart type based on data shape (e.g., line for time series, bar for categories, scatter for numeric vs numeric).

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| result_df | `pandas.DataFrame` (or rows+cols) | `execute_sql` or cache | yes |
| question | `str` | User message | no (to infer intent) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| chart_config | `dict` (Plotly layout + data) | Included in API response; rendered by frontend |
| chart_type | `str` | UI label |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| LLM (optional) | choose chart type if ambiguous | If LLM fails, fall back to heuristics (e.g., column types) |

## Business Rules

- Do not make network calls; generate pure JSON.
- If data exceeds 5 000 points, downsample or aggregate for browser performance.
- Always include axis labels derived from column names.
- For single‑column results, show a metric card instead of a chart.
- If no meaningful chart is possible, return `null` and UI shows a data table.

## Success Criteria

- [ ] Chart spec validates against Plotly schema (< 100 ms generation).
- [ ] ≥ 80 % of test charts are renderable in a headless browser.
- [ ] Downsampling preserves visible trends.
