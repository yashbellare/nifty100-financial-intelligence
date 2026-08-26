-- Sprint 1 exploratory queries
-- 1. Table row counts
SELECT 'companies' table_name, COUNT(*) row_count FROM companies UNION ALL SELECT 'profitandloss',COUNT(*) FROM profitandloss UNION ALL SELECT 'balancesheet',COUNT(*) FROM balancesheet UNION ALL SELECT 'cashflow',COUNT(*) FROM cashflow UNION ALL SELECT 'analysis',COUNT(*) FROM analysis UNION ALL SELECT 'documents',COUNT(*) FROM documents UNION ALL SELECT 'prosandcons',COUNT(*) FROM prosandcons UNION ALL SELECT 'sectors',COUNT(*) FROM sectors UNION ALL SELECT 'stock_prices',COUNT(*) FROM stock_prices UNION ALL SELECT 'market_cap',COUNT(*) FROM market_cap UNION ALL SELECT 'financial_ratios',COUNT(*) FROM financial_ratios UNION ALL SELECT 'peer_groups',COUNT(*) FROM peer_groups;
-- 2. FK integrity
PRAGMA foreign_key_check;
-- 3. Duplicate annual keys
SELECT company_id,year,COUNT(*) n FROM profitandloss GROUP BY company_id,year HAVING n>1;
-- 4. P&L year coverage per company
SELECT company_id,COUNT(DISTINCT year) years FROM profitandloss GROUP BY company_id ORDER BY years,company_id;
-- 5. BS year coverage per company
SELECT company_id,COUNT(DISTINCT year) years FROM balancesheet GROUP BY company_id ORDER BY years,company_id;
-- 6. CF year coverage per company
SELECT company_id,COUNT(DISTINCT year) years FROM cashflow GROUP BY company_id ORDER BY years,company_id;
-- 7. Null audit on key fields
SELECT SUM(company_id IS NULL) null_company_id, SUM(year IS NULL) null_year, SUM(sales IS NULL) null_sales FROM profitandloss;
-- 8. Companies with <5 years in any core statement
WITH c AS (SELECT id FROM companies), p AS (SELECT company_id,COUNT(DISTINCT year) n FROM profitandloss GROUP BY company_id), b AS (SELECT company_id,COUNT(DISTINCT year) n FROM balancesheet GROUP BY company_id), f AS (SELECT company_id,COUNT(DISTINCT year) n FROM cashflow GROUP BY company_id) SELECT c.id,COALESCE(p.n,0) pl_years,COALESCE(b.n,0) bs_years,COALESCE(f.n,0) cf_years FROM c LEFT JOIN p ON p.company_id=c.id LEFT JOIN b ON b.company_id=c.id LEFT JOIN f ON f.company_id=c.id WHERE MIN(COALESCE(p.n,0),COALESCE(b.n,0),COALESCE(f.n,0))<5;
-- 9. Latest-year sample join
WITH latest AS (SELECT company_id,MAX(year) year FROM profitandloss GROUP BY company_id) SELECT p.company_id,p.year,p.sales,p.net_profit,b.total_assets,f.operating_activity FROM profitandloss p JOIN latest l USING(company_id,year) LEFT JOIN balancesheet b USING(company_id,year) LEFT JOIN cashflow f USING(company_id,year) LIMIT 20;
-- 10. Sector coverage
SELECT s.broad_sector,COUNT(*) companies FROM sectors s GROUP BY s.broad_sector ORDER BY companies DESC;
-- 11. Orphan check across all child tables
SELECT 'profitandloss' table_name,COUNT(*) orphan_rows FROM profitandloss p LEFT JOIN companies c ON c.id=p.company_id WHERE c.id IS NULL UNION ALL SELECT 'balancesheet',COUNT(*) FROM balancesheet b LEFT JOIN companies c ON c.id=b.company_id WHERE c.id IS NULL UNION ALL SELECT 'cashflow',COUNT(*) FROM cashflow f LEFT JOIN companies c ON c.id=f.company_id WHERE c.id IS NULL UNION ALL SELECT 'sectors',COUNT(*) FROM sectors s LEFT JOIN companies c ON c.id=s.company_id WHERE c.id IS NULL;
