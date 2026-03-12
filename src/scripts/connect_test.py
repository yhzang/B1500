import pyvisa
import time
import csv
from io import StringIO

VISA_ADDR = "GPIB0::17::INSTR"

rm = pyvisa.ResourceManager()
print("Resources:", rm.list_resources())

inst = rm.open_resource(VISA_ADDR)
inst.write_termination = "\n"
inst.read_termination = None
inst.timeout = 20000
inst.query_delay = 0.05

try:
    inst.clear()
except Exception:
    pass

def q(cmd: str) -> str:
    inst.write(cmd)
    return inst.read().strip()

def pop_errx():
    inst.write("ERRX?")
    s = inst.read().strip()
    row = next(csv.reader(StringIO(s)))
    code = int(row[0])
    msg = row[1] if len(row) > 1 else ""
    return code, msg

def drain_err(max_n=50):
    for _ in range(max_n):
        code, msg = pop_errx()
        if code == 0:
            print("ERRX?: 0 (No Error)")
            return
        print(f"ERRX?: {code} -> {msg}")

try:
    inst.write("*RST")
    drain_err()

    print("*IDN? ->", q("*IDN?"))
    print("*OPC? ->", q("*OPC?"))

    drain_err()
finally:
    inst.close()
    rm.close()
    print("Done.")