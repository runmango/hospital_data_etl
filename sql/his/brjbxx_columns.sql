select column_name, data_type, data_length, nullable
from all_tab_columns
where owner = 'JK_WSB'
and table_name = 'BRJBXX'
order by column_id

