"""Make the intelligence packages importable without an exported PYTHONPATH.

`pytest intelligence/tests` failed with ModuleNotFoundError: No module named
'crc' because the conformal package is a plain directory, not an installed
distribution, and pytest does not add it to sys.path. Requiring the caller to
remember `PYTHONPATH=intelligence/conformal` is a step that will be forgotten
exactly once, in the run whose result matters -- so the test suite states its
own import paths here instead.
"""
import pathlib
import sys

INTELLIGENCE = pathlib.Path(__file__).resolve().parents[1]
for package_dir in ("conformal", "causal", "counterfactual", "inference", "models", "training"):
    candidate = INTELLIGENCE / package_dir
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
