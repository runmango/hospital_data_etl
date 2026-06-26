-- Keyword predicates are built in Python with bind parameters.
-- Example predicate: upper(column_name) like :keyword_0
select owner, table_name, column_name, data_type, data_length, nullable, column_id
from all_tab_columns
where owner not in ('SYS','SYSTEM','XDB','MDSYS','CTXSYS','ORDSYS','DBSNMP')
order by owner, table_name, column_name
