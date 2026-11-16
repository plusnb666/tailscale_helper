class TscpError(Exception):
    """Base class for expected command errors."""


class ConfigError(TscpError):
    """Raised when alias configuration is missing or invalid."""


class UnknownAliasError(ConfigError):
    """Raised when a requested alias does not exist."""


class TargetError(TscpError):
    """Raised when an alias target cannot be parsed or resolved."""


class TransferError(TscpError):
    """Raised when SCP cannot be started or fails."""
