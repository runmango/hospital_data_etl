select column_name, data_type, data_length, nullable, column_id
from all_tab_columns
where owner = upper(:owner)
and table_name = upper(:table_name)
order by column_id
