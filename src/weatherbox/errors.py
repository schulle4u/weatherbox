"""Application-specific exception hierarchy."""


class WeatherboxError(Exception):
    """Base error for expected application failures."""


class ConfigurationError(WeatherboxError):
    """Raised when application or localization configuration is invalid."""


class WeatherUnavailableError(WeatherboxError):
    """Raised when no sufficiently recent weather forecast is available."""


class TemplateRenderError(WeatherboxError):
    """Raised when an announcement template cannot be rendered safely."""


class TTSGenerationError(WeatherboxError):
    """Raised when a text-to-speech provider fails to create valid audio."""


class AudioProcessingError(WeatherboxError):
    """Raised when audio conversion or validation fails."""


class AssetPublicationError(WeatherboxError):
    """Raised when a generated audio asset cannot be published."""
