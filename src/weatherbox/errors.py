class WeatherboxError(Exception):
    """Base error for expected application failures."""


class ConfigurationError(WeatherboxError):
    pass


class WeatherUnavailableError(WeatherboxError):
    pass


class TemplateRenderError(WeatherboxError):
    pass


class TTSGenerationError(WeatherboxError):
    pass


class AudioProcessingError(WeatherboxError):
    pass


class AssetPublicationError(WeatherboxError):
    pass

