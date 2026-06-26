select *
from jk_wsb.brzdqk
where brxh in (
select brxh
from jk_wsb.brjbxx
where cyrq between to_date(:start_date, 'YYYYMMDD')
and to_date(:end_date, 'YYYYMMDD') + 0.99999
)

