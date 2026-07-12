from __future__ import annotations

from pprint import pprint
import sys

from services.enterprise_scheduler import run_with_retries


def main() -> int:
    result = run_with_retries()
    pprint(result)

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
