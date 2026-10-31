import json
import sys


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: test_lock.py <tour_lock> <layered_lock>")
    tour_lock_path = sys.argv[1]
    layered_lock_path = sys.argv[2]

    with open(tour_lock_path, "r", encoding="utf-8") as f:
        tour_data = json.load(f)
    with open(layered_lock_path, "r", encoding="utf-8") as f:
        layered_data = json.load(f)

    tour_pkgs = sorted(p["name"] for p in tour_data.get("packages", []))
    expected_tour = ["mystery-devel", "tour"]
    assert tour_pkgs == expected_tour, f"Expected {expected_tour}, got {tour_pkgs}"

    layered_pkgs = sorted(p["name"] for p in layered_data.get("packages", []))
    expected_layered = ["tour"]
    assert layered_pkgs == expected_layered, f"Expected {expected_layered}, got {layered_pkgs}"

    print("rpm_lock verification passed!")


if __name__ == "__main__":
    main()
