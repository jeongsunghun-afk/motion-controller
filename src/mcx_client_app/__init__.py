"""mcx_client_app package

Expose core classes and the package version.
"""

from .McxClientApp import McxClientApp, McxClientAppThread, StopSignal, ThreadSafeValue
from .McxClientAppConfiguration import McxClientAppConfiguration
from .state_def import StateCommand, State
from .McxWatchdog import McxWatchdog

# Version exposed at package level for convenience
from ._version import __version__, get_version  # noqa: F401

__all__ = [
	"McxClientApp",
	"McxClientAppThread",
	"StopSignal",
	"ThreadSafeValue",
	"McxClientAppConfiguration",
	"StateCommand",
	"State",
	"McxWatchdog",
	"__version__",
	"get_version",
]

