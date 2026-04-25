from __future__ import annotations

from codepilot.core.config import get_settings
from codepilot.core.redis_client import ping_redis


def main() -> None:
    settings = get_settings()
    print({"redis": ping_redis(settings), "repo": str(settings.repo_path)})


if __name__ == "__main__":
    main()
