"""
Configuration management for the Swiper application.

This module provides the ConfigurationManager class for loading, parsing,
validating, and accessing all application configuration including TOML
settings and YAML holiday calendars.
"""

import sys
from pathlib import Path
from datetime import date
from typing import Any

# Handle Python 3.10 vs 3.11+ TOML support
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError(
            "tomli is required for Python < 3.11. Install with: pip install tomli"
        )

import yaml
from pydantic import BaseModel, ValidationError as PydanticValidationError, field_validator

from swiper.models import ConfigSettings, PolicySettings, DataSettings, ReportingPeriod
from swiper.exceptions import ConfigurationError


class PolicySettingsModel(BaseModel):
    """Pydantic model for validating policy settings."""
    required_days_per_period: int

    @field_validator('required_days_per_period')
    @classmethod
    def validate_required_days(cls, v: int) -> int:
        """Validate that required days is positive."""
        if v <= 0:
            raise ValueError('required_days_per_period must be greater than 0')
        return v


class DataSettingsModel(BaseModel):
    """Pydantic model for validating data settings."""
    reporting_periods_file: str
    exclusion_days_file: str
    attendance_data_dir: str


class ConfigSettingsModel(BaseModel):
    """Pydantic model for validating main configuration."""
    policy: PolicySettingsModel
    data: DataSettingsModel


class ReportingPeriodModel(BaseModel):
    """Pydantic model for validating reporting period definitions."""
    period_number: int
    start_date: date
    end_date: date
    report_date: date

    @field_validator('period_number')
    @classmethod
    def validate_period_number(cls, v: int) -> int:
        """Validate that period number is positive."""
        if v <= 0:
            raise ValueError('period_number must be greater than 0')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        """Validate that end_date is after start_date."""
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError('end_date must be after or equal to start_date')
        return v


class ConfigurationManager:
    """
    Manages all application configuration.

    Loads and validates configuration from TOML files (main config and reporting periods)
    and YAML files (holiday calendar), providing type-safe access to all settings.

    Attributes:
        _config_path: Path to the main configuration file
        _project_root: Root directory of the project
        _settings: Validated ConfigSettings instance
        _reporting_periods: List of validated ReportingPeriod instances
        _exclusion_days: List of exclusion day dates
    """

    def __init__(self, config_path: Path = Path("config/config.toml")):
        """
        Initialize and load configuration.

        Args:
            config_path: Path to the main configuration file (relative to project root)

        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid

        Implements: Requirement 1.1
        """
        self._config_path = config_path
        self._project_root = Path.cwd()
        self._settings: ConfigSettings | None = None
        self._reporting_periods: list[ReportingPeriod] = []
        self._exclusion_days: list[date] = []

        # Load all configuration on initialization
        self._load_all()

    def _load_all(self) -> None:
        """Load all configuration files."""
        self._settings = self.load_config()
        self._reporting_periods = self.load_reporting_periods()
        self._exclusion_days = self.load_exclusion_days()

    def load_config(self) -> ConfigSettings:
        """
        Load main configuration from TOML.

        Returns:
            Validated ConfigSettings instance

        Raises:
            ConfigurationError: If file is missing, has invalid syntax, or fails validation

        Implements: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
        """
        config_file = self._project_root / self._config_path

        # Check if file exists (Req 1.2)
        if not config_file.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self._config_path}"
            )

        # Load and parse TOML (Req 1.3)
        try:
            with open(config_file, 'rb') as f:
                config_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Invalid TOML syntax in {self._config_path}: {e}"
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read {self._config_path}: {e}"
            )

        # Validate structure with Pydantic (Req 1.4, 1.5)
        try:
            validated = ConfigSettingsModel(**config_data)
        except PydanticValidationError as e:
            errors = []
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                errors.append(f"{field}: {error['msg']}")
            raise ConfigurationError(
                f"Configuration validation failed:\n" + "\n".join(errors)
            )

        # Convert to application models (Req 1.9)
        policy = PolicySettings(
            required_days_per_period=validated.policy.required_days_per_period
        )
        data = DataSettings(
            reporting_periods_file=validated.data.reporting_periods_file,
            exclusion_days_file=validated.data.exclusion_days_file,
            attendance_data_dir=validated.data.attendance_data_dir
        )

        return ConfigSettings(policy=policy, data=data)

    def load_reporting_periods(self) -> list[ReportingPeriod]:
        """
        Load reporting period definitions from TOML.

        Returns:
            List of validated ReportingPeriod instances

        Raises:
            ConfigurationError: If file is missing or periods are invalid

        Implements: Requirements 1.6, 1.7
        """
        if not self._settings:
            raise ConfigurationError("Main configuration must be loaded first")

        periods_file = self._project_root / self._settings.data.reporting_periods_file

        # Check if file exists
        if not periods_file.exists():
            raise ConfigurationError(
                f"Reporting periods file not found: {self._settings.data.reporting_periods_file}"
            )

        # Load and parse TOML
        try:
            with open(periods_file, 'rb') as f:
                periods_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Invalid TOML syntax in reporting periods file: {e}"
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read reporting periods file: {e}"
            )

        # Validate periods
        if 'periods' not in periods_data:
            raise ConfigurationError(
                "Reporting periods file must contain a 'periods' array"
            )

        periods: list[ReportingPeriod] = []
        for period_dict in periods_data['periods']:
            try:
                validated = ReportingPeriodModel(**period_dict)
            except PydanticValidationError as e:
                errors = []
                for error in e.errors():
                    field = '.'.join(str(loc) for loc in error['loc'])
                    errors.append(f"{field}: {error['msg']}")
                raise ConfigurationError(
                    f"Invalid reporting period definition:\n" + "\n".join(errors)
                )

            # Create ReportingPeriod with placeholder values for calculated fields
            # These will be populated by ReportingPeriodCalculator in Phase 5
            if not self._settings:
                raise ConfigurationError("Settings not loaded")

            period = ReportingPeriod(
                period_number=validated.period_number,
                start_date=validated.start_date,
                end_date=validated.end_date,
                report_date=validated.report_date,
                baseline_required_days=self._settings.policy.required_days_per_period,
                exclusion_days=[],  # Will be calculated later
                effective_required_days=self._settings.policy.required_days_per_period  # Will be calculated later
            )
            periods.append(period)

        return periods

    def load_exclusion_days(self) -> list[date]:
        """
        Load holiday calendar from YAML.

        Returns:
            List of exclusion day dates

        Raises:
            ConfigurationError: If file is missing or YAML is invalid

        Implements: Requirement 1.8
        """
        if not self._settings:
            raise ConfigurationError("Main configuration must be loaded first")

        exclusions_file = self._project_root / self._settings.data.exclusion_days_file

        # Check if file exists
        if not exclusions_file.exists():
            raise ConfigurationError(
                f"Exclusion days file not found: {self._settings.data.exclusion_days_file}"
            )

        # Load and parse YAML
        try:
            with open(exclusions_file, 'r') as f:
                exclusions_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML syntax in exclusion days file: {e}"
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read exclusion days file: {e}"
            )

        # Extract holidays list
        if not exclusions_data or 'holidays' not in exclusions_data:
            raise ConfigurationError(
                "Exclusion days file must contain a 'holidays' list"
            )

        # Convert to date objects
        exclusion_days: list[date] = []
        for holiday in exclusions_data['holidays']:
            if isinstance(holiday, date):
                exclusion_days.append(holiday)
            else:
                raise ConfigurationError(
                    f"Invalid holiday date format: {holiday}"
                )

        return exclusion_days

    def validate_all(self) -> bool:
        """
        Validate all configuration files.

        Returns:
            True if all configuration is valid

        Raises:
            ConfigurationError: If any configuration is invalid

        Implements: Requirement 9.2
        """
        # Configuration is validated during load, so if we get here, it's valid
        # This method exists for explicit validation requests
        return True

    def get_settings(self) -> ConfigSettings:
        """
        Access validated settings.

        Returns:
            ConfigSettings instance

        Implements: Requirement 1.9
        """
        if not self._settings:
            raise ConfigurationError("Configuration not loaded")
        return self._settings

    def get_reporting_periods(self) -> list[ReportingPeriod]:
        """
        Access validated reporting periods.

        Returns:
            List of ReportingPeriod instances

        Implements: Requirement 1.9
        """
        return self._reporting_periods.copy()

    def get_exclusion_days(self) -> list[date]:
        """
        Access validated exclusion days.

        Returns:
            List of exclusion day dates

        Implements: Requirement 1.9
        """
        return self._exclusion_days.copy()
