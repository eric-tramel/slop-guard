"""Version helpers for package and CLI metadata."""

from importlib.metadata import version

PACKAGE_NAME = "slop-guard"
PACKAGE_VERSION: str = version(PACKAGE_NAME)
