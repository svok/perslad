import time; import subprocess;
def measure_rate_limit():	start_time = time.time();	subprocess.run(["python", "/workspace/rate_limit_test.py"]);	elapsed_time = time.time() - start_time;	print(f"Elapsed time: {elapsed_time:.2f} seconds")
for _ in range(5):		measure_rate_limit()
