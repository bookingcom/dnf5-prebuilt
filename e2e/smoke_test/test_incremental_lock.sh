#!/usr/bin/env bash
set -euo pipefail

LOCK_ALREADY_INSTALLED="$1"
LOCK_INCREMENTAL="$2"
LOCK_BOTH="$3"
LOCK_CHANGED_INTEGRITY="$4"

echo "=== Verifying Incremental Lockfile Scenarios ==="

python3 -c '
import json
import sys

def load(path):
    """The requested names and the names of the locked packages of a lockfile."""
    with open(path) as f:
        d = json.load(f)
    return d.get("requested", []), [p["name"] for p in d.get("packages", [])]

# Test 1: Re-requesting already installed package with same integrity
req1, names1 = load(sys.argv[1])
assert req1 == ["tour"], f"Expected requested=[tour], got {req1}"
assert len(names1) == 0, f"Expected 0 packages, got {len(names1)}"
print("Scenario 1 passed: Already installed package is in requested but not in packages.")

# Test 2: Incremental request of a new package
req2, names2 = load(sys.argv[2])
assert req2 == ["mystery-devel"], f"Expected requested=[mystery-devel], got {req2}"
assert "mystery-devel" in names2, "mystery-devel should be in packages"
assert "tour" not in names2, "tour should NOT be in packages"
print("Scenario 2 passed: Incremental new package resolved without reinstalling previous layer packages.")

# Test 3: Requesting both already-installed and new package
req3, names3 = load(sys.argv[3])
assert sorted(req3) == ["mystery-devel", "tour"], f"Expected requested=[mystery-devel, tour], got {sorted(req3)}"
assert "mystery-devel" in names3, "mystery-devel should be in packages"
assert "tour" not in names3, "tour should NOT be in packages"
print("Scenario 3 passed: Requested both; only incremental uninstalled package present in packages.")

# Test 4: Package with changed integrity
req4, names4 = load(sys.argv[4])
assert req4 == ["tour"], f"Expected requested=[tour], got {req4}"
assert "tour" in names4, "tour SHOULD be in packages because its integrity changed"
print("Scenario 4 passed: Package with changed integrity is re-included in packages.")

print("ALL INCREMENTAL LOCK TESTS PASSED!")
' "${LOCK_ALREADY_INSTALLED}" "${LOCK_INCREMENTAL}" "${LOCK_BOTH}" "${LOCK_CHANGED_INTEGRITY}"
