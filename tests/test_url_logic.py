#!/usr/bin/env python3
"""Test URL construction logic for HTTP peer polling."""

test_cases = [
    ("node2", "http://node2:8080/temp"),
    ("192.168.1.102", "http://192.168.1.102:8080/temp"),
    ("http://node2:8080/temp", "http://node2:8080/temp"),
    ("http://node2", "http://node2:8080/temp"),
    ("http://node2:8080", "http://node2:8080/temp"),
    ("nanocluster2.internal", "http://nanocluster2.internal:8080/temp"),
]

print("Testing URL construction logic:\n")
all_pass = True

for input_url, expected in test_cases:
    # Simulate the URL construction logic
    url = input_url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}:8080/temp"
    elif ":" not in url.split("://", 1)[1]:
        url = f"{url}:8080/temp"
    elif not url.endswith("/temp") and not url.endswith("/metrics"):
        url = f"{url}/temp"

    passed = url == expected
    all_pass = all_pass and passed
    status = "✓" if passed else "✗"
    print(f"{status} {input_url:30s} -> {url}")
    if not passed:
        print(f"  Expected: {expected}")

print()
if all_pass:
    print("All tests passed! ✓")
else:
    print("Some tests failed! ✗")
    exit(1)
