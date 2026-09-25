"""Integration checks against disposable Postgres only; no production connection."""
import os
import sys
from pathlib import Path
import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from company_enrichment import run

with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as c:
    page='<script type="application/ld+json">{"@type":"Organization","name":"Fixture Company","legalName":"Fixture LLC"}</script>'
    status,counts=run(c,lambda url:(page,url))
    assert status=='success' and counts['candidate']==1
    candidate=c.execute('SELECT candidate_id FROM company_enrichment_candidates').fetchone()[0]
    c.execute("UPDATE company_enrichment_candidates SET status='rejected' WHERE candidate_id=%s",(candidate,))
    c.execute("UPDATE company_enrichment_sources SET last_attempt_at=now()-interval '8 days'")
    status,counts=run(c,lambda url:(page,url))
    assert counts['candidate']==0
    assert c.execute('SELECT status FROM company_enrichment_candidates').fetchone()[0]=='rejected'
    c.execute("UPDATE company_enrichment_sources SET last_attempt_at=now()-interval '8 days'")
    def failed(url):raise TimeoutError('Do not store this private URL: '+url)
    status,counts=run(c,failed)
    assert status=='failed' and counts['failed']==1
    assert c.execute('SELECT last_error FROM company_enrichment_sources').fetchone()[0]=='TimeoutError'
    assert c.execute("SELECT legal_name FROM company_private_profiles WHERE company_id='fixture-company'").fetchone()[0] is None
    assert c.execute("SELECT parent_name FROM company_sales_accounts WHERE sales_account_id='fixture-account'").fetchone()[0]=='Legacy Parent'
print('COMPANY_ENRICHMENT_WORKER=PASS')
