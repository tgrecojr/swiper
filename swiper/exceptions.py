"""
Custom exception classes for the Swiper application.

This module defines all custom exceptions used throughout the application
for consistent error handling and reporting.
"""


class SwiperException(Exception):
    """
    Base exception for all application errors.

    All custom exceptions in the Swiper application inherit from this base class,
    making it easy to catch all application-specific errors with a single except clause.
    """
    pass


class ConfigurationError(SwiperException):
    """
    Raised when configuration is invalid or cannot be loaded.

    This exception is raised when:
    - Configuration files are missing or cannot be read
    - TOML/YAML syntax is invalid
    - Required configuration fields are missing
    - Configuration values fail validation (e.g., invalid types, out of range)

    Implements Requirements 1.2, 1.3, 1.5, and 1.7.

    Examples:
        >>> raise ConfigurationError("Configuration file not found: config/config.toml")
        >>> raise ConfigurationError("Invalid TOML syntax at line 5: Expected '='")
        >>> raise ConfigurationError("Missing required field: policy.required_days_per_period")
    """
    pass


class StorageError(SwiperException):
    """
    Raised when file I/O operations fail.

    This exception is raised when:
    - Attendance data files cannot be read or written
    - JSON parsing fails on attendance files
    - File system permissions prevent operations
    - Disk space or other I/O errors occur

    Implements Requirements 10.2 and 11.4.

    Examples:
        >>> raise StorageError("Failed to write attendance data: Permission denied")
        >>> raise StorageError("Invalid JSON in file data/attendance_2025.json: Unexpected token")
        >>> raise StorageError("Invalid attendance status 'out-of-office' at date 2025-08-15")
    """
    pass


class ValidationError(SwiperException):
    """
    Raised when data validation fails.

    This exception is raised when:
    - A date falls outside all defined reporting periods
    - Data values fail business logic validation
    - Invalid arguments are provided to functions

    Implements Requirement 3.2.

    Examples:
        >>> raise ValidationError("No reporting period defined for date 2025-12-25")
        >>> raise ValidationError("Invalid date format: expected YYYY-MM-DD")
    """
    pass
