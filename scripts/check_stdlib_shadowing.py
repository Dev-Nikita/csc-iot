"""No script in analysis/ may import a stdlib module a sibling file shadows."""
import os, re, sys
d = "analysis"
stdlib = set(sys.stdlib_module_names)
shadowed = {f[:-3] for f in os.listdir(d) if f.endswith(".py") and f[:-3] in stdlib}
bad = []
for f in sorted(os.listdir(d)):
    if not f.endswith(".py") or f[:-3] in shadowed:
        continue
    src = open(os.path.join(d, f), encoding="utf-8").read()
    for name in shadowed:
        if re.search(rf"^\s*import {name}\b|^\s*from {name}\b", src, re.M):
            bad.append(f"{d}/{f} imports '{name}', which {d}/{name}.py shadows")
for b in bad:
    print("  " + b)
sys.exit(1 if bad else 0)
