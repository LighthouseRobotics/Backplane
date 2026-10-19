#!/usr/bin/env python3
"""Hash the installed Bend engine directory without assuming a single binary."""
import hashlib, pathlib, sys
root=pathlib.Path(sys.argv[1])
if root.is_file():files=[root]
elif root.is_dir():files=sorted(p for p in root.rglob('*') if p.is_file())
else:raise SystemExit('missing toolchain engine: '+str(root))
if not files:raise SystemExit('empty toolchain engine: '+str(root))
for path in files:print(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path))
