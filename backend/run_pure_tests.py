"""Runs the dependency-free tests (campaign matching) with plain Python.
Usage, from the backend folder:  python run_pure_tests.py
No pip install needed."""
import sys

sys.path.insert(0, ".")
import tests.test_matching as t

failed = 0
for name in sorted(n for n in dir(t) if n.startswith("test_")):
    try:
        getattr(t, name)()
        print("PASS", name)
    except Exception as e:  # noqa: BLE001
        failed += 1
        print("FAIL", name, "->", repr(e))
print("\nAll good." if not failed else f"\n{failed} test(s) failed.")
sys.exit(1 if failed else 0)
