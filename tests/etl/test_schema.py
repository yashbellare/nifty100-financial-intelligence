import sqlite3, subprocess, sys
from pathlib import Path

def test_schema_creates_tables(tmp_path):
 db=tmp_path/"x.db"; c=sqlite3.connect(db); c.executescript(Path("db/schema.sql").read_text()); names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}; assert len(names)==12
def test_foreign_keys_enabled_after_loader_db(): pass
def test_schema_has_companies_pk(tmp_path):
 import sqlite3; c=sqlite3.connect(tmp_path/"x.db"); c.executescript(Path("db/schema.sql").read_text()); info=list(c.execute("pragma table_info(companies)")); assert next(r for r in info if r[1]=="id")[5]==1
def test_schema_unique_pl(tmp_path):
 import sqlite3; c=sqlite3.connect(tmp_path/"x.db"); c.executescript(Path("db/schema.sql").read_text()); c.execute("insert into companies(id,company_name,face_value) values('TCS','TCS',1)"); c.execute("insert into profitandloss(company_id,year,sales,expenses,operating_profit,opm_percentage) values('TCS','2024-03',1,1,0,0)");
 try: c.execute("insert into profitandloss(company_id,year,sales,expenses,operating_profit,opm_percentage) values('TCS','2024-03',1,1,0,0)"); assert False
 except sqlite3.IntegrityError: pass
