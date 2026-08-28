"""Sprint 2 ratio-engine population runner."""
from pathlib import Path
import sqlite3, logging, math, sys
import pandas as pd
import numpy as np

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from src.analytics.ratios import *
from src.analytics.cagr import cagr

DB=BASE/"nifty100.db"
OUT=BASE/"output"
OUT.mkdir(exist_ok=True)
LOG=OUT/"ratio_edge_cases.log"

def fnum(x):
    return None if pd.isna(x) else float(x)

def year_int(s):
    try: return int(str(s)[:4])
    except: return None

def compute():
    conn=sqlite3.connect(DB)
    # Ensure Sprint 2 schema is applied even when Sprint 1 DB already exists.
    conn.execute("DROP TABLE IF EXISTS financial_ratios")
    conn.executescript((BASE/"db/schema.sql").read_text())
    pl=pd.read_sql("SELECT * FROM profitandloss",conn)
    bs=pd.read_sql("SELECT * FROM balancesheet",conn)
    cf=pd.read_sql("SELECT * FROM cashflow",conn)
    companies=pd.read_sql("SELECT * FROM companies",conn)
    sectors=pd.read_sql("SELECT * FROM sectors",conn)
    # Normalize source data to numeric.
    for df in (pl,bs,cf):
        for c in df.columns:
            if c not in ("company_id","year"): df[c]=pd.to_numeric(df[c],errors="coerce")
    face_map=companies.set_index("id")["face_value"].to_dict()
    source_roce=companies.set_index("id")["roce_percentage"].to_dict()
    source_roe=companies.set_index("id")["roe_percentage"].to_dict()
    # Financials ROCE is assessed relative to the same-year Financials median.
    sector_map=sectors.set_index("company_id")["broad_sector"].to_dict()

    # Join per-company-year on union of all available financial statements.
    keys=pd.concat([pl[["company_id","year"]],bs[["company_id","year"]],cf[["company_id","year"]]]).drop_duplicates()
    keys=keys.sort_values(["company_id","year"]).reset_index(drop=True)
    pl=pl.set_index(["company_id","year"]); bs=bs.set_index(["company_id","year"]); cf=cf.set_index(["company_id","year"])
    log_rows=[]
    rows=[]
    for _,k in keys.iterrows():
        cid,year=k.company_id,k.year
        p=pl.loc[(cid,year)] if (cid,year) in pl.index else pd.Series(dtype=float)
        b=bs.loc[(cid,year)] if (cid,year) in bs.index else pd.Series(dtype=float)
        c=cf.loc[(cid,year)] if (cid,year) in cf.index else pd.Series(dtype=float)
        def g(df,key): return fnum(df[key]) if key in df.index else None
        sales,op,npf,oi,interest,eps,div=g(p,"sales"),g(p,"operating_profit"),g(p,"net_profit"),g(p,"other_income"),g(p,"interest"),g(p,"eps"),g(p,"dividend_payout")
        eq,res,borrow,inv,assets=g(b,"equity_capital"),g(b,"reserves"),g(b,"borrowings"),g(b,"investments"),g(b,"total_assets")
        cfo,cfi,cff=g(c,"operating_activity"),g(c,"investing_activity"),g(c,"financing_activity")
        npm=net_profit_margin(npf,sales); opm=operating_profit_margin(op,sales)
        cross,diff=opm_crosscheck(opm,g(p,"opm_percentage"))
        if cross:
            log_rows.append((cid,year,"OPM","data source issue",f"Computed {opm:.4f} vs source {g(p,'opm_percentage'):.4f}; diff {diff:.4f} pp"))
        roe=return_on_equity(npf,eq,res)
        roce=return_on_capital_employed(op,eq,res,borrow)
        roa=return_on_assets(npf,assets)
        de=debt_to_equity(borrow,eq,res)
        sector=sector_map.get(cid)
        # Compute same-year Financials peer median ROCE from companies with valid inputs.
        fin_roces=[]
        for fid in sectors.loc[sectors.broad_sector.eq("Financials"),"company_id"].tolist():
            if (fid,year) in pl.index and (fid,year) in bs.index:
                fp=pl.loc[(fid,year)]; fb=bs.loc[(fid,year)]
                fv=return_on_capital_employed(fnum(fp.get("operating_profit")),fnum(fb.get("equity_capital")),fnum(fb.get("reserves")),fnum(fb.get("borrowings")))
                if fv is not None: fin_roces.append(fv)
        roce_benchmark=(float(np.median(fin_roces)) if fin_roces else None) if sector=="Financials" else None
        roce_relative=(roce-roce_benchmark) if roce is not None and roce_benchmark is not None else None
        hlf=high_leverage_flag(de,sector)
        icr=interest_coverage(op,oi,interest)
        icrl=interest_coverage_label(icr)
        icrw=interest_warning(icr)
        nd=net_debt(borrow,inv)
        turnover=asset_turnover(sales,assets)
        fcf=free_cash_flow(cfo,cfi) if cfo is not None or cfi is not None else None
        capexcr=capex(cfi)
        capint=capex_intensity(cfi,sales)
        capintl=capex_intensity_label(capint)
        fconv=fcf_conversion_rate(fcf,op)
        bvps=book_value_per_share(eq,res,face_map.get(cid,10) or 10)
        # 5-year CFO/PAT quality is calculated from the last five available company years.
        patrat=[]
        for yy,rr in pl.loc[cid].iterrows() if cid in pl.index.get_level_values(0) else []:
            pat=fnum(rr.get("net_profit")); cfo_v=fnum(cf.loc[(cid,yy)]["operating_activity"]) if (cid,yy) in cf.index else None
            if pat is not None and pat != 0 and cfo_v is not None: patrat.append(cfo_v/pat)
        score=cfo_quality_score(patrat[-5:])
        scorelabel=cfo_quality_label(score)
        pattern=capital_allocation_pattern(cfo,cfi,cff,(cfo/npf if cfo is not None and npf not in (None,0) else None))
        def growth(metric):
            series=[]
            source=pl if metric in ("revenue","pat","eps") else None
            for yy,rr in source.loc[cid].iterrows() if cid in source.index.get_level_values(0) else []:
                val={"revenue":rr.get("sales"),"pat":rr.get("net_profit"),"eps":rr.get("eps")}[metric]
                yi=year_int(yy); val=fnum(val)
                if yi is not None and val is not None: series.append((yi,val))
            out={}
            endyear=max([x[0] for x in series],default=None)
            for n in (3,5,10):
                cand=[(y,v) for y,v in series if endyear is not None and y<=endyear-n]
                if not cand:
                    out[n]=(None,"INSUFFICIENT")
                else:
                    sy,sv=max(cand,key=lambda x:x[0])
                    ev=dict(series)[endyear]
                    out[n]=cagr(sv,ev,endyear-sy)
            return out
        rev= growth("revenue"); patg=growth("pat"); epsg=growth("eps")
        # Compare company-level source ratios with computed ratio for traceability.
        if roce is not None and source_roce.get(cid) is not None and abs(roce-source_roce[cid])>5:
            log_rows.append((cid,year,"ROCE","data source issue",f"Computed {roce:.4f} vs company source {source_roce[cid]:.4f}; difference {roce-source_roce[cid]:.4f} pp"))
        if roe is not None and source_roe.get(cid) is not None and abs(roe-source_roe[cid])>5:
            cat="data source issue" if cid=="TCS" else "version difference"
            log_rows.append((cid,year,"ROE",cat,f"Computed {roe:.4f} vs company source {source_roe[cid]:.4f}; difference {roe-source_roe[cid]:.4f} pp"))
        # Composite score: transparent 0-100 quality score, using available dimensions.
        parts=[]
        if roe is not None: parts.append(min(max(roe/20*25,0),25))
        if opm is not None: parts.append(min(max(opm/20*20,0),20))
        if de is not None: parts.append(20 if de<=1 else max(0,20-(de-1)*4))
        if icr is not None: parts.append(min(max(icr/5*15,0),15))
        if score is not None: parts.append(min(max(score/1.5*20,0),20))
        composite=sum(parts) if parts else None
        row=[cid,year,npm,opm,roe,roce,roce_benchmark,roce_relative,roa,de,int(hlf),icr,icrl,int(icrw),nd,turnover,fcf,capexcr,capint,capintl,eps,bvps,div,borrow,cfo,score,scorelabel,fconv,pattern]
        for dct in (rev,patg,epsg):
            for n in (3,5,10): row += [dct[n][0],dct[n][1]]
        row += [composite]
        rows.append(row)

    cols=["company_id","year","net_profit_margin_pct","operating_profit_margin_pct","return_on_equity_pct","return_on_capital_employed_pct","roce_sector_benchmark_pct","roce_vs_sector_benchmark_pct","return_on_assets_pct","debt_to_equity","high_leverage_flag","interest_coverage","icr_label","icr_warning_flag","net_debt_cr","asset_turnover","free_cash_flow_cr","capex_cr","capex_intensity_pct","capex_intensity_label","earnings_per_share","book_value_per_share","dividend_payout_ratio_pct","total_debt_cr","cash_from_operations_cr","cfo_quality_score","cfo_quality_label","fcf_conversion_rate_pct","capital_allocation_pattern"]
    for metric in ("revenue","pat","eps"):
        for n in (3,5,10): cols += [f"{metric}_cagr_{n}yr",f"{metric}_cagr_{n}yr_flag"]
    cols += ["composite_quality_score"]
    df=pd.DataFrame(rows,columns=cols)
    conn.execute("DELETE FROM financial_ratios")
    df.to_sql("financial_ratios",conn,if_exists="append",index=False)
    # Capital allocation output for every company-year with cash-flow data.
    alloc=df[df["cash_from_operations_cr"].notna()].copy()
    # Recover signs from original cashflow to preserve zero explicitly.
    cfo2=cf.reset_index()
    alloc2=cfo2.merge(df[["company_id","year","capital_allocation_pattern"]],on=["company_id","year"],how="left")
    def sign(x): return "+" if x>0 else "-" if x<0 else "0"
    alloc2["cfo_sign"]=alloc2.operating_activity.map(sign); alloc2["cfi_sign"]=alloc2.investing_activity.map(sign); alloc2["cff_sign"]=alloc2.financing_activity.map(sign)
    alloc2[["company_id","year","cfo_sign","cfi_sign","cff_sign","capital_allocation_pattern"]].rename(columns={"capital_allocation_pattern":"pattern_label"}).to_csv(OUT/"capital_allocation.csv",index=False)
    with open(LOG,"w",encoding="utf8") as fh:
        fh.write("# Sprint 2 ratio edge-case log\n")
        fh.write("# Categories: data source issue, version difference, formula discrepancy\n")
        for cid,year,metric,cat,msg in log_rows:
            fh.write(f"{cid} | {year} | {metric} | {cat} | {msg}\n")
        if not log_rows: fh.write("No anomalies detected.\n")
    conn.commit()
    # checks
    count=conn.execute("select count(*) from financial_ratios").fetchone()[0]
    conn.close()
    return df,count,len(log_rows)

if __name__=="__main__":
    df,count,logs=compute()
    print(f"financial_ratios rows={count}; edge_case_entries={logs}; companies={df.company_id.nunique()}; columns={len(df.columns)}")
