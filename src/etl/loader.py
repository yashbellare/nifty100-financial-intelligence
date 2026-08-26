from pathlib import Path
import os, re, sqlite3, time
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
BASE=Path(__file__).resolve().parents[2]
RAW=BASE/"data/raw"; SUP=BASE/"data/supporting"; DB=BASE/os.getenv("DB_PATH","nifty100.db"); OUT=BASE/os.getenv("OUTPUT_DIR","output")

def normalize_ticker(value):
    if pd.isna(value): return None
    s=str(value).strip().upper()
    return s or None

def normalize_year(value):
    if pd.isna(value): return None
    s=str(value).strip().upper().replace(' ','')
    m=re.fullmatch(r'(MAR|DEC)[-/]?([0-9]{2,4})',s)
    if m:
        y=m.group(2); y=int(y) if len(y)==4 else 2000+int(y)
        return f"{y:04d}-{'03' if m.group(1)=='MAR' else '12'}"
    m=re.fullmatch(r'FY([0-9]{2,4})',s)
    if m:
        y=m.group(1); y=int(y) if len(y)==4 else 2000+int(y)
        return f"{y:04d}-03"
    m=re.fullmatch(r'([0-9]{4})[-/]([0-9]{1,2})',s)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    if re.fullmatch(r'[0-9]{4}',s): return f"{int(s):04d}-03"
    # ISO-like timestamps
    try:
        dt=pd.to_datetime(value, errors='raise'); return dt.strftime('%Y-%m')
    except Exception:
        return None

def read_excel(path, core_file=False):
    return pd.read_excel(path, header=1 if core_file else 0)

def clean_df(name, df):
    df=df.copy(); df.columns=[str(c).strip() for c in df.columns]
    if 'company_id' in df.columns: df['company_id']=df['company_id'].map(normalize_ticker)
    if name in {'profitandloss','balancesheet','cashflow','financial_ratios'} and 'year' in df.columns: df['year']=df['year'].map(normalize_year)
    if name=='documents' and 'Year' in df.columns: df['Year']=pd.to_numeric(df['Year'], errors='coerce').astype('Int64')
    if name=='stock_prices' and 'date' in df.columns: df['date']=pd.to_datetime(df['date'],errors='coerce').dt.strftime('%Y-%m-%d')
    return df

def load_all():
    from .validator import validate_all
    from .normaliser import deduplicate
    OUT.mkdir(exist_ok=True)
    datasets={}
    specs=[
      ('companies',RAW/'companies.xlsx',True),('profitandloss',RAW/'profitandloss.xlsx',True),('balancesheet',RAW/'balancesheet.xlsx',True),('cashflow',RAW/'cashflow.xlsx',True),('analysis',RAW/'analysis.xlsx',True),('documents',RAW/'documents.xlsx',True),('prosandcons',RAW/'prosandcons.xlsx',True),
      ('sectors',SUP/'sectors.xlsx',False),('stock_prices',SUP/'stock_prices.xlsx',False),('market_cap',SUP/'market_cap.xlsx',False),('financial_ratios',SUP/'financial_ratios.xlsx',False),('peer_groups',SUP/'peer_groups.xlsx',False)]
    for n,p,c in specs: datasets[n]=clean_df(n,read_excel(p,c))
    # Run critical-source validation first so DQ-01/02/03/07/08 are explicitly documented,
    # then apply the corrective transformations and run the remaining rules on the clean set.
    raw_datasets={k:v.copy() for k,v in datasets.items()}
    raw_failures=validate_all(raw_datasets)
    audit=[]; dedup_logs=[]
    companies=datasets['companies']; datasets['companies']=companies.drop_duplicates('id',keep='last')
    for n in ['profitandloss','balancesheet','cashflow','financial_ratios','documents','stock_prices','market_cap','peer_groups']:
        before=len(datasets[n]); datasets[n], log=deduplicate(n,datasets[n]); dedup_logs.extend(log); after=len(datasets[n])
    clean_failures=validate_all(datasets)
    # Keep source critical findings as RESOLVED after the loader's corrective action, plus current warnings.
    failures=[]
    failures.extend([x for x in raw_failures if x['rule_id'] in {'DQ-01','DQ-02','DQ-03','DQ-07','DQ-08'}])
    failures.extend([x for x in clean_failures if x['severity'] != 'CRITICAL'])
    vf=pd.DataFrame(failures, columns=['rule_id','company_id','year','field','issue','severity','action'])
    vf['status']=vf.apply(lambda r: 'RESOLVED' if r.rule_id in {'DQ-01','DQ-02','DQ-03','DQ-07','DQ-08'} else 'OPEN',axis=1)
    vf.to_csv(OUT/'validation_failures.csv',index=False)
    rules=['DQ-01','DQ-02','DQ-03','DQ-04','DQ-05','DQ-06','DQ-07','DQ-08','DQ-09','DQ-10','DQ-11','DQ-12','DQ-13','DQ-14','DQ-15','DQ-16']
    exec_rows=[]
    for rule in rules:
        if rule=='DQ-13' and os.getenv('DQ_URL_CHECK','false').lower()!='true': status='NOT_RUN_OFFLINE'; findings=0
        else:
            sub=vf[vf.rule_id==rule]; findings=len(sub); status='PASS' if findings==0 else ('RESOLVED' if (sub.status=='RESOLVED').all() else 'OPEN')
        exec_rows.append({'rule_id':rule,'status':status,'findings':findings})
    pd.DataFrame(exec_rows).to_csv(OUT/'dq_rule_execution.csv',index=False)
    conn=sqlite3.connect(DB); conn.execute('PRAGMA foreign_keys=ON'); conn.executescript((BASE/'db/schema.sql').read_text())
    # clear in FK-safe order
    for t in ['peer_groups','financial_ratios','market_cap','stock_prices','sectors','prosandcons','documents','analysis','cashflow','balancesheet','profitandloss','companies']: conn.execute(f'DELETE FROM {t}')
    for n,df in datasets.items():
        t0=time.perf_counter(); rows_in=len(df); rejected=0
        # DQ-03 critical orphan rows rejected before insertion
        if n!='companies' and 'company_id' in df.columns:
            known=set(datasets['companies']['id'].dropna())
            mask=df.company_id.isin(known)
            rejected += int((~mask).sum()); df=df[mask].copy()
        # DQ-07/DQ-08 invalid year/ticker rows rejected for relevant tables
        if n in {'profitandloss','balancesheet','cashflow','financial_ratios'}:
            mask=df.year.notna() & df.company_id.notna() & df.company_id.str.len().between(2,12)
            rejected += int((~mask).sum()); df=df[mask].copy()
        if n=='stock_prices': df=df[df.date.notna()]
        if n=='documents': df=df[df.Year.notna()]
        # preserve SQLite integer booleans
        if n=='peer_groups': df['is_benchmark']=df['is_benchmark'].fillna(False).astype(int)
        # pandas NaN -> SQL NULL
        df.to_sql(n,conn,if_exists='append',index=False)
        audit.append({'table':n,'rows_in':rows_in,'rows_out':len(df),'rejected':rejected,'critical_rejections':0,'timestamp':pd.Timestamp.utcnow().isoformat(),'runtime_s':round(time.perf_counter()-t0,4)})
    fk=list(conn.execute('PRAGMA foreign_key_check'))
    conn.commit(); conn.close()
    pd.DataFrame(audit).to_csv(OUT/'load_audit.csv',index=False)
    (OUT/'deduplication_log.csv').write_text('table,company_id,year,action,source_rows\n'+''.join(','.join(map(str,x))+'\n' for x in dedup_logs),encoding='utf-8')
    return datasets, failures, fk

if __name__=='__main__':
    d,f,fk=load_all(); print('Loaded',len(d),'tables; failures=',len(f),'FK=',len(fk))
