import pandas as pd
import requests
import streamlit as st

from src.dashboard.utils.db import get_companies, get_documents


@st.cache_data(ttl=3600)
def check_report(url):
	if not url or pd.isna(url):
		return False, "Report unavailable"
	try:
		response = requests.head(str(url), allow_redirects=True, timeout=3)
		if response.status_code == 405:
			response = requests.get(str(url), stream=True, allow_redirects=True, timeout=3)
		return response.status_code < 400, f"HTTP {response.status_code}"
	except requests.RequestException:
		return False, "Report unavailable"


companies = get_companies().copy()
st.title("Annual reports")
st.caption("Browse the available BSE annual report links for a company.")
search = st.text_input("Search company", placeholder="Type a company name or ticker")
search_text = search.strip().lower()
matches = companies if not search_text else companies[
	companies["company_id"].astype(str).str.lower().str.contains(search_text, na=False)
	| companies["company_name"].astype(str).str.lower().str.contains(search_text, na=False)
]
if matches.empty:
	st.warning("Ticker not found - please try another")
	st.stop()

labels = {row.company_id: f"{row.company_name} ({row.company_id})" for row in matches.itertuples()}
ticker = st.selectbox("Company", matches["company_id"].tolist(), format_func=lambda value: labels.get(value, value))
documents = get_documents(ticker).copy()
if documents.empty:
	st.info("No annual reports are available for this company.")
	st.stop()

documents["year"] = pd.to_numeric(documents.get("year"), errors="coerce")
documents = documents.sort_values("year", ascending=False)
rows = []
for _, report in documents.iterrows():
	url = report.get("annual_report")
	available, status = check_report(url)
	rows.append({"Year": int(report["year"]) if pd.notna(report["year"]) else "N/A", "url": url, "available": available, "status": status})

st.subheader(f"Reports for {labels.get(ticker, ticker)}")
for report in rows:
	year, url, available, status = report["Year"], report["url"], report["available"], report["status"]
	if available:
		st.markdown(f"**{year}**  |  [Open BSE annual report]({url})  |  :green[Available]")
	else:
		st.markdown(f"**{year}**  |  :red[Report unavailable] ({status})")
