import subprocess
import time

# Use pexpect-like approach via stdin
proc = subprocess.Popen(
    ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=no',
     '-o', 'PasswordAuthentication=yes',
     '-p', '13210', 'root@ssh5.aiccloud.one'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

time.sleep(5)
proc.stdin.write('CLgrfq64QZSc3okc\n')
proc.stdin.flush()
time.sleep(3)

stdout, stderr = proc.communicate(timeout=10)
print("STDOUT:", stdout)
print("STDERR:", stderr)
