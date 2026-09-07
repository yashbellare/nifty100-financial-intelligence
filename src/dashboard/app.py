import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/01_home.py", title="Home", icon=":material/home:"),
    st.Page("pages/02_profile.py", title="Company profile", icon=":material/business:"),
    st.Page("pages/03_screener.py", title="Screener", icon=":material/search:"),
    st.Page("pages/04_peers.py", title="Peer comparison", icon=":material/groups:"),
    st.Page("pages/05_trends.py", title="Trend analysis", icon=":material/show_chart:"),
    st.Page("pages/06_sectors.py", title="Sector analysis", icon=":material/domain:"),
    st.Page("pages/07_capital.py", title="Capital allocation", icon=":material/account_tree:"),
    st.Page("pages/08_reports.py", title="Annual reports", icon=":material/description:"),
]

navigation = st.navigation(pages)
navigation.run()