import pandas as pd

def normalize_ticker(value):
    if pd.isna(value): return None
    s=str(value).strip().upper(); return s or None

def normalize_year(value):
    from .loader import normalize_year as _ny
    return _ny(value)

def deduplicate(name, df):
    keys={
      'profitandloss':['company_id','year'],'balancesheet':['company_id','year'],'cashflow':['company_id','year'],
      'financial_ratios':['company_id','year'],'documents':['company_id','Year'],'stock_prices':['company_id','date'],'market_cap':['company_id','year'],'peer_groups':['peer_group_name','company_id']
    }.get(name)
    if not keys: return df.copy(), []
    dup=df[df.duplicated(keys,keep=False)].copy(); logs=[]
    if len(dup):
        for vals,g in dup.groupby(keys,dropna=False): logs.append((name,*([str(v) for v in (vals if isinstance(vals,tuple) else (vals,))]),'keep_last',len(g)))
    return df.drop_duplicates(keys,keep='last').reset_index(drop=True),logs
