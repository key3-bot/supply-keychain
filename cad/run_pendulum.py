import os
import sys
import traceback

print("start-pendulum", flush=True)
try:
    path = "/home/node/supply-keychain/cad/build_assembly.py"
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    exec(compile(source, path, "exec"), {"__name__": "__main__"})
    print("pendulum-ok", flush=True)
except Exception:
    traceback.print_exc()
    os._exit(1)
os._exit(0)
