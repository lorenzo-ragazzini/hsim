from datetime import datetime; t = datetime.now()
from hsim.GSOM.GSOMGame import main; main('data/profiler/GSOM_original.xlsx', app=True)
print((datetime.now() - t).total_seconds())
