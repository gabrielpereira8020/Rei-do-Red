class FootballIntelligenceError(Exception):
    """Base exception for the shadow Football Intelligence Engine."""


class InvalidInputError(FootballIntelligenceError):
    """Raised when a domain input is malformed or outside accepted bounds."""


class InsufficientDataError(FootballIntelligenceError):
    """Raised when the engine cannot safely estimate a probability."""
