select column_name, data_type, data_length, nullable
from all_tab_columns
where owner = 'JK_WSB'
and table_name = 'BRZDQK'
order by column_id

