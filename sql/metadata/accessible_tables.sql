select owner, table_name, num_rows, last_analyzed
from all_tables
where (:owner is null or owner = upper(:owner))
and (:table_name_like is null or table_name like upper(:table_name_like))
order by owner, table_name
