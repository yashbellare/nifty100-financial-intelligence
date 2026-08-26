import re, os
import pandas as pd


def _fail(rule, company, year, field, issue, sev, action):
    return {'rule_id':rule,'company_id':None if pd.isna(company) else str(company),'year':None if pd.isna(year) else str(year),'field':field,'issue':issue,'severity':sev,'action':action}

def validate_all(d):
    out=[]; companies=d['companies']; ids=set(companies['id'].dropna())
    # DQ01
    dup=companies[companies.duplicated('id',keep=False)]
    for _,r in dup.iterrows(): out.append(_fail('DQ-01',r.id,None,'id','Duplicate company primary key','CRITICAL','Remove duplicate / investigate'))
    # DQ02
    for n in ['profitandloss','balancesheet','cashflow']:
        x=d[n]; dup=x[x.duplicated(['company_id','year'],keep=False)]
        for _,r in dup.iterrows(): out.append(_fail('DQ-02',r.company_id,r.year,'company_id,year',f'Duplicate annual key in {n}','CRITICAL','Deduplicate keeping last occurrence'))
    # DQ03
    for n,x in d.items():
        if 'company_id' in x.columns:
            for _,r in x[~x.company_id.isin(ids)].iterrows(): out.append(_fail('DQ-03',r.company_id,r.get('year',r.get('Year','')),'company_id',f'Orphan company_id found in {n}','CRITICAL','Reject orphan row'))
    # DQ04
    bs=d['balancesheet'].copy(); bs_valid=bs[bs.year.fillna('').astype(str).str.fullmatch(r'\d{4}-\d{2}')].copy() if 'year' in bs.columns else bs.copy(); denom=bs_valid.total_assets.replace(0,pd.NA)
    bad=bs_valid[(abs(bs_valid.total_assets-bs_valid.total_liabilities)/denom>0.01)]
    for _,r in bad.iterrows(): out.append(_fail('DQ-04',r.company_id,r.year,'total_assets,total_liabilities','Balance sheet imbalance >1%','WARNING','Flag for analyst review'))
    # DQ05
    pl=d['profitandloss'].copy(); pl_valid=pl[pl.year.fillna('').astype(str).str.fullmatch(r'\d{4}-\d{2}')].copy() if 'year' in pl.columns else pl.copy(); calc=pl_valid.operating_profit/pl_valid.sales*100
    bad=pl_valid[(pl_valid.sales!=0)&((pl_valid.opm_percentage-calc).abs()>=1.0)]
    for _,r in bad.iterrows(): out.append(_fail('DQ-05',r.company_id,r.year,'opm_percentage','Source OPM differs from computed OPM by >=1 pp','WARNING','Use computed OPM in Ratio Engine'))
    # DQ06
    sectors=d['sectors']; bank=set(sectors[sectors.sub_sector.fillna('').str.contains('Bank',case=False,na=False)].company_id)
    bad=pl_valid[(pl_valid.sales<=0)&(~pl_valid.company_id.isin(bank))]
    for _,r in bad.iterrows(): out.append(_fail('DQ-06',r.company_id,r.year,'sales','Sales <= 0 for non-bank company','WARNING','Flag and exclude from CAGR'))
    # DQ07
    for n in ['profitandloss','balancesheet','cashflow','financial_ratios']:
        x=d[n]
        if 'year' not in x.columns: continue
        bad=x[~x.year.fillna('').astype(str).str.fullmatch(r'\d{4}-\d{2}')]
        for _,r in bad.iterrows(): out.append(_fail('DQ-07',r.company_id,r.year,'year','Unparseable year format','CRITICAL','Reject row'))
    # DQ08
    for n,x in d.items():
        if 'company_id' in x.columns:
            bad=x[x.company_id.fillna('').map(lambda s:not (2<=len(str(s))<=12 and str(s)==str(s).strip().upper()))]
            for _,r in bad.iterrows(): out.append(_fail('DQ-08',r.company_id,r.get('year',r.get('Year','')),'company_id','Ticker outside 2-12 uppercase characters','CRITICAL','Normalise or reject'))
    # DQ09
    cf=d['cashflow']; cf_valid=cf[cf.year.fillna('').astype(str).str.fullmatch(r'\d{4}-\d{2}')].copy() if 'year' in cf.columns else cf.copy(); mismatch=abs(cf_valid.net_cash_flow-(cf_valid.operating_activity+cf_valid.investing_activity+cf_valid.financing_activity))>10
    for _,r in cf_valid[mismatch].iterrows(): out.append(_fail('DQ-09',r.company_id,r.year,'net_cash_flow','Net cash differs from CFO+CFI+CFF by >10 Cr','WARNING','Recompute net cash from components'))
    # DQ10
    bad=bs_valid[bs_valid.fixed_assets<0]
    for _,r in bad.iterrows(): out.append(_fail('DQ-10',r.company_id,r.year,'fixed_assets','Negative fixed assets','WARNING','Coerce to 0 and log'))
    # DQ11
    bad=pl_valid[(pl_valid.tax_percentage<0)|(pl_valid.tax_percentage>60)]
    for _,r in bad.iterrows(): out.append(_fail('DQ-11',r.company_id,r.year,'tax_percentage','Tax rate outside 0-60%','WARNING','Flag for analyst review'))
    # DQ12
    bad=pl_valid[pl_valid.dividend_payout>200]
    for _,r in bad.iterrows(): out.append(_fail('DQ-12',r.company_id,r.year,'dividend_payout','Dividend payout >200%','WARNING','Flag for analyst confirmation'))
    # DQ13: network check is intentionally optional/offline-safe. Loader records the rule in report metadata.
    docs=d['documents'];
    if os.getenv('DQ_URL_CHECK','false').lower()=='true':
        import requests
        for _,r in docs[docs.Annual_Report.notna()].iterrows():
            try:
                status=requests.head(r.Annual_Report,timeout=5,allow_redirects=True).status_code
                if status!=200: out.append(_fail('DQ-13',r.company_id,r.Year,'Annual_Report',f'HTTP status {status}','WARNING','Log URL; do not reject'))
            except Exception as e: out.append(_fail('DQ-13',r.company_id,r.Year,'Annual_Report',f'URL check error: {type(e).__name__}','WARNING','Log URL check error'))
    # DQ14
    bad=pl_valid[(pl_valid.net_profit>0)&(pl_valid.eps<=0)]
    for _,r in bad.iterrows(): out.append(_fail('DQ-14',r.company_id,r.year,'eps','EPS <= 0 while net profit > 0','WARNING','Flag mismatch; review source'))
    # DQ15 informational
    bad=bs_valid[bs_valid.total_assets!=bs_valid.total_liabilities]
    for _,r in bad.iterrows(): out.append(_fail('DQ-15',r.company_id,r.year,'total_assets,total_liabilities','Strict assets/liabilities mismatch','INFO','Informational counter'))
    # DQ16 coverage
    for cid in companies.id:
        counts=[len(d[n].loc[(d[n].company_id==cid) & d[n].year.fillna('').astype(str).str.fullmatch(r'\d{4}-\d{2}'),'year'].dropna().unique()) for n in ['profitandloss','balancesheet','cashflow']]
        if min(counts)<5: out.append(_fail('DQ-16',cid,None,'coverage',f'Coverage below 5 years: P&L={counts[0]}, BS={counts[1]}, CF={counts[2]}','WARNING','Flag company; exclude from CAGR if <3 years'))
    return out
