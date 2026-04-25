from __future__ import annotations

from codepilot.core.config import get_settings
from codepilot.indexer.repo import index_repository


def main() -> None:
    settings = get_settings()
    result = index_repository(settings.repo_path, settings.chroma_path)
    print(result)


if __name__ == "__main__":
    main()
