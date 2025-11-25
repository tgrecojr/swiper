"""
Data models for the Swiper application.

This module defines all dataclasses used throughout the application for
type-safe data representation and communication between components.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass
class PolicySettings:
    """
    Policy configuration for attendance requirements.

    Attributes:
        required_days_per_period: Baseline minimum in-office days per reporting period
    """
    required_days_per_period: int  # Baseline requirement (typically 20)


@dataclass
class DataSettings:
    """
    File paths for data storage.

    Attributes:
        reporting_periods_file: Path to TOML file containing reporting period definitions
        exclusion_days_file: Path to YAML file containing holiday calendar
        attendance_data_dir: Directory path for attendance JSON files
    """
    reporting_periods_file: str
    exclusion_days_file: str
    attendance_data_dir: str


@dataclass
class ConfigSettings:
    """
    Main application configuration.

    Combines policy settings and data file paths into a single configuration object.
    Implements Requirement 1.4.

    Attributes:
        policy: Policy settings for attendance requirements
        data: File paths for configuration and data storage
    """
    policy: PolicySettings
    data: DataSettings


@dataclass
class ReportingPeriod:
    """
    Represents a reporting period with configurable duration.

    Period duration is determined by the configured start_date and end_date,
    not by any assumed fixed length. Different periods can have different durations.
    Implements Requirement 3.5.

    Attributes:
        period_number: Unique identifier for the period (e.g., 1, 2, 3...)
        start_date: First day of the reporting period (inclusive)
        end_date: Last day of the reporting period (inclusive)
        report_date: Date by which compliance must be reported
        baseline_required_days: Required in-office days from configuration (e.g., 20)
        exclusion_days: List of holidays/shutdowns that fall within this period
        effective_required_days: Actual required days after subtracting exclusions
    """
    period_number: int
    start_date: date
    end_date: date
    report_date: date
    baseline_required_days: int
    exclusion_days: list[date]
    effective_required_days: int


@dataclass
class AttendanceRecord:
    """
    Represents a single day's attendance status.

    Implements Requirement 2.6.

    Attributes:
        date: The date of the attendance record
        status: Either "in-office" or "remote"
    """
    date: date
    status: Literal["in-office", "remote"]


@dataclass
class ComplianceStatus:
    """
    Compliance evaluation for a reporting period.

    Contains all information needed to determine if an employee is meeting
    their in-office attendance requirements, including predictive risk analysis.
    Implements Requirements 6.8 and 12.2-12.6.

    Attributes:
        period: The reporting period being evaluated
        in_office_count: Number of days recorded as "in-office" in this period
        required_count: Effective required days (after exclusions)
        workdays_remaining: Number of workdays left in the period from today
        is_compliant: True if in_office_count >= required_count
        days_short: How many more in-office days needed (0 if compliant)
        days_ahead: How many extra in-office days recorded (0 if not compliant)
        compliance_risk: Risk level for achieving compliance
            - "achieved": Already compliant
            - "impossible": Cannot achieve compliance (days_short > workdays_remaining)
            - "critical": Must be in-office every remaining day (days_short == workdays_remaining)
            - "at-risk": Need >75% in-office attendance for remaining days
            - "possible": Can still achieve compliance with reasonable attendance
    """
    period: ReportingPeriod
    in_office_count: int
    required_count: int
    workdays_remaining: int
    is_compliant: bool
    days_short: int
    days_ahead: int
    compliance_risk: Literal["impossible", "critical", "at-risk", "possible", "achieved"]
