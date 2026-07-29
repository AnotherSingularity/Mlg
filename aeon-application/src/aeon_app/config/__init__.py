"""aeon_app.config — versioned configuration schemas + resolver."""
from .schemas import (
    ApplicationConfig,
    BackendConfig,
    ClockConfig,
    ConfigError,
    FeedbackConfig,
    InferenceConfig,
    ObservabilityConfig,
    ProjectionConfig,
    RecursionConfig,
    SnapshotConfig,
    SourceConfig,
    TrainingConfig,
    reference_config,
    resolve,
)
from .language_lock import (
    LanguageLockError,
    LanguageLockRecord,
    load_lock,
    verify_language_lock,
)

__all__ = [
    "ApplicationConfig",
    "SourceConfig",
    "ProjectionConfig",
    "RecursionConfig",
    "ClockConfig",
    "FeedbackConfig",
    "BackendConfig",
    "TrainingConfig",
    "InferenceConfig",
    "SnapshotConfig",
    "ObservabilityConfig",
    "ConfigError",
    "resolve",
    "reference_config",
    "LanguageLockError",
    "LanguageLockRecord",
    "load_lock",
    "verify_language_lock",
]
