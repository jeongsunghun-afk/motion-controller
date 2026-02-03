"""Package version information for mcx_client_app.

Keep a single source of truth for the package version here. Tools and
users can import `src.mcx_client_app.__version__` or call
`src.mcx_client_app.get_version()` to access the value.
"""
__version__ = "0.2.1"

def get_version() -> str:
    """Return the package version string.

    Returns:
        str: Semver-like version string.
    """
    return __version__
