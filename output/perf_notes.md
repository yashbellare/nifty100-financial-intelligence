# Day 43 Performance Notes

- Concurrent screener calls: 10 completed in 0.109s (target: <= 10s).
- Screener request median/max: 0.094s / 0.106s.
- Five dashboard ratio loads: median/max 0.112s / 0.149s (target: <= 3s each).
- SQLite indexes applied for company/year joins and peer-group lookups.
- API and Streamlit use separate ports by default: 8000 and 8501.
