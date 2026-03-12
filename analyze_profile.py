import pstats

# Load the profiler stats
stats = pstats.Stats("data/profiler/output.prof")

# Sort by cumulative time (time spent in function and all subfunctions)
print("=" * 80)
print("TOP 30 FUNCTIONS BY CUMULATIVE TIME")
print("=" * 80)
stats.sort_stats('cumulative')
stats.print_stats(30)

print("\n" + "=" * 80)
print("TOP 30 FUNCTIONS BY TOTAL TIME (excluding subfunctions)")
print("=" * 80)
stats.sort_stats('time')
stats.print_stats(30)

print("\n" + "=" * 80)
print("TOP 30 MOST CALLED FUNCTIONS")
print("=" * 80)
stats.sort_stats('calls')
stats.print_stats(30)

# Get callers for a specific bottleneck function (example)
print("\n" + "=" * 80)
print("CALLERS OF TOP 10 EXPENSIVE FUNCTIONS")
print("=" * 80)
stats.sort_stats('cumulative')
stats.print_callers(10)
