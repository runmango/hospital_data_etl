-- Keyword predicates are built in Python with bind parameters.
-- Example predicate: upper(table_name) like :keyword_0
select owner, table_name, num_rows, last_analyzed
from all_tables
where owner not in ('SYS','SYSTEM','XDB','MDSYS','CTXSYS','ORDSYS','DBSNMP')
order by owner, table_name
