import pytest
from src.etl.loader import normalize_year, normalize_ticker

@pytest.mark.parametrize("raw,expected", [
("Mar-23","2023-03"),("FY24","2024-03"),("Dec-22","2022-12"),("Mar 2014","2014-03"),("Dec 2012","2012-12"),("2024","2024-03"),("2024-03","2024-03"),("2024/3","2024-03"),("Mar-2024","2024-03"),("Dec-2024","2024-12"),(" mar-23 ","2023-03"),("FY2024","2024-03"),("2020-01","2020-01"),(None,None),("xyz",None),("","None")])
def test_normalize_year(raw,expected):
    assert normalize_year(raw)==(None if expected=="None" else expected)

@pytest.mark.parametrize("raw,expected", [(" tcs ","TCS"),("tcs","TCS"),("TCS","TCS"),(" TCS\n","TCS"),(None,None),(" infy ","INFY")])
def test_normalize_ticker(raw,expected): assert normalize_ticker(raw)==expected

# additional edge tests
def test_year_invalid_text(): assert normalize_year("abc") is None
def test_year_dec_boundary(): assert normalize_year("Dec-99")=="2099-12"
def test_year_fy_boundary(): assert normalize_year("FY00")=="2000-03"
def test_ticker_empty(): assert normalize_ticker("   ") is None
def test_ticker_mixed_case(): assert normalize_ticker("aDaNi") == "ADANI"
def test_ticker_numeric_cast(): assert normalize_ticker(123)=="123"
def test_year_numeric(): assert normalize_year(2024)=="2024-03"
def test_year_timestamp(): assert normalize_year("2024-03-31")=="2024-03"
