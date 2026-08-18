import os
import sys
import traceback

print("CAD_ROOT", os.environ.get("CAD_ROOT"))
try:
    path = "/home/node/supply-keychain/cad/build_assembly.py"
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    exec(compile(source, path, "exec"), {"__name__": "__main__"})
except SystemExit as exc:
    print("exit", exc.code)
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
