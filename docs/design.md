# Design Document

## Overview

This document provides detailed technical specifications for implementing the In-Office Attendance Tracking Application. Each component from the architectural blueprint is elaborated with specific interfaces, data structures, and implementation guidance.

## Design Principles

1. **Type Safety**: Use Python type hints throughout with dataclasses for data models
2. **Configuration as Code**: Validate all configuration with Pydantic models
3. **Single Responsibility**: Each component has one clear purpose
4. **Fail Fast**: Validate early and provide clear error messages
5. **Idempotency**: Operations like recording attendance can be repeated safely
6. **Atomic Operations**: File writes use atomic patterns to prevent corruption

## Project Structure

```
swiper/
├── swiper/
│   ├── __init__.py
│   ├── __main__.py              # Entry point for CLI
│   ├── cli.py                   # CLIInterface component
│   ├── config.py                # ConfigurationManager component
│   ├── models.py                # Data models (dataclasses)
│   ├── storage.py               # AttendanceStore component
│   ├── reporting.py             # ReportingPeriodCalculator component
│   ├── compliance.py            # ComplianceChecker component
│   ├── business_days.py         # BusinessDayCalculator component
│   └── exceptions.py            # Custom exception classes
├── config/
│   ├── config.toml              # Main application configuration
│   ├── reporting_periods.toml  # Reporting period definitions
│   └── holidays.yaml            # Holiday calendar (business-python format)
├── data/
│   └── attendance_YYYY.json    # Annual attendance records (gitignored)
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_storage.py
│   ├── test_reporting.py
│   ├── test_compliance.py
│   ├── test_business_days.py
│   ├── test_cli.py
│   └── fixtures/
├── docs/
│   ├── phase0_research.md
│   ├── blueprint.md
│   ├── requirements.md
│   ├── design.md (this file)
│   ├── tasks.md (to be generated)
│   └── validation.md (to be generated)
├── requirements.txt
├── setup.py
├── README.md
└── .gitignore
```

## Data Models

### Location: `swiper/models.py`

#### ConfigSettings
```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PolicySettings:
    """Policy configuration for attendance requirements."""
    required_days_per_period: int  # Default 20
    period_length_weeks: int       # Default 13

@dataclass
class DataSettings:
    """File paths for data storage."""
    reporting_periods_file: str
    exclusion_days_file: str
    attendance_data_dir: str

@dataclass
class ConfigSettings:
    """Main application configuration. Implements Req 1.4."""
    policy: PolicySettings
    data: DataSettings
```

#### ReportingPeriod
```python
from dataclasses import dataclass
from datetime import date
from typing import List

@dataclass
class ReportingPeriod:
    """Represents a 13-week reporting period. Implements Req 3.5."""
    period_number: int
    start_date: date
    end_date: date
    deadline: date
    baseline_required_days: int        # From config (e.g., 20)
    exclusion_days: List[date]         # Holidays within this period
    effective_required_days: int       # baseline - weekday exclusions
```

#### AttendanceRecord
```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass
class AttendanceRecord:
    """Represents a single day's attendance status. Implements Req 2.6."""
    date: date
    status: Literal["in-office", "remote"]
```

#### ComplianceStatus
```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ComplianceStatus:
    """Compliance evaluation for a reporting period. Implements Req 6.8, 12.2-12.6."""
    period: ReportingPeriod
    in_office_count: int               # Days recorded as in-office
    required_count: int                # Effective required days
    workdays_remaining: int            # Workdays left in period
    is_compliant: bool                 # True if in_office_count >= required_count
    days_short: int                    # required - in_office (max 0)
    days_ahead: int                    # in_office - required (max 0)
    compliance_risk: Literal["impossible", "critical", "at-risk", "possible", "achieved"]
```

## Custom Exceptions

### Location: `swiper/exceptions.py`

```python
class SwiperException(Exception):
    """Base exception for all application errors."""
    pass

class ConfigurationError(SwiperException):
    """Raised when configuration is invalid. Implements Req 1.2, 1.3, 1.5, 1.7."""
    pass

class StorageError(SwiperException):
    """Raised when file I/O operations fail. Implements Req 10.2, 11.4."""
    pass

class ValidationError(SwiperException):
    """Raised when data validation fails. Implements Req 3.2."""
    pass
```

## Component Specifications

### Component: ConfigurationManager

**Purpose**: Load, parse, validate, and provide access to all configuration data
**Location**: `swiper/config.py`
**Implements**: Requirements 1 (all criteria)

#### Interface

```python
from pathlib import Path
from typing import List
from datetime import date
from swiper.models import ConfigSettings, ReportingPeriod

class ConfigurationManager:
    """Manages all application configuration."""

    def __init__(self, config_path: Path = Path("config/config.toml")):
        """Initialize and load configuration. Implements Req 1.1."""
        pass

    def load_config(self) -> ConfigSettings:
        """Load main configuration from TOML. Implements Req 1.1-1.5."""
        pass

    def load_reporting_periods(self) -> List[ReportingPeriod]:
        """Load reporting period definitions. Implements Req 1.6-1.7."""
        pass

    def load_exclusion_days(self) -> List[date]:
        """Load holiday calendar from YAML. Implements Req 1.8."""
        pass

    def validate_all(self) -> bool:
        """Validate all configuration files. Implements Req 9.2."""
        pass

    def get_settings(self) -> ConfigSettings:
        """Access validated settings. Implements Req 1.9."""
        pass

    def get_reporting_periods(self) -> List[ReportingPeriod]:
        """Access validated reporting periods. Implements Req 1.9."""
        pass

    def get_exclusion_days(self) -> List[date]:
        """Access validated exclusion days. Implements Req 1.9."""
        pass
```

#### Implementation Notes

- Use `tomllib` (Python 3.11+) or `tomli` (Python 3.10) for TOML parsing
- Use `pyyaml` for YAML parsing
- Use Pydantic models for validation (Req 1.4)
- Raise `ConfigurationError` with descriptive messages for all validation failures (Req 1.2, 1.3, 1.5, 1.7)
- Cache loaded configuration after initial validation

### Component: AttendanceStore

**Purpose**: Persist daily attendance records to JSON files and retrieve historical data
**Location**: `swiper/storage.py`
**Implements**: Requirements 2 (criteria 2.6-2.10), 11 (all criteria)

#### Interface

```python
from pathlib import Path
from datetime import date
from typing import Dict, List, Literal
from swiper.models import AttendanceRecord

class AttendanceStore:
    """Handles persistence of attendance records."""

    def __init__(self, data_dir: Path):
        """Initialize with data directory path. Implements Req 11.5."""
        pass

    def save_record(self, record: AttendanceRecord) -> None:
        """Save attendance record to appropriate year file. Implements Req 2.6-2.10, 11.1."""
        pass

    def load_records(self, start_date: date, end_date: date) -> List[AttendanceRecord]:
        """Load attendance records for date range. Implements Req 6.1, 11.2-11.4."""
        pass

    def get_records_for_year(self, year: int) -> Dict[str, str]:
        """Load all records for a specific year. Implements Req 11.2-11.4."""
        pass

    def _ensure_data_dir(self) -> None:
        """Create data directory if missing. Implements Req 2.7, 11.6."""
        pass

    def _get_year_file_path(self, year: int) -> Path:
        """Get path to JSON file for a year."""
        pass

    def _atomic_write(self, file_path: Path, data: Dict) -> None:
        """Write JSON atomically to prevent corruption. Implements Req 11.1."""
        pass

    def _validate_record_data(self, data: Dict) -> None:
        """Validate JSON structure and values. Implements Req 11.2-11.4."""
        pass
```

#### Implementation Notes

- JSON file format: `{"2025-08-15": "in-office", "2025-08-16": "remote"}`
- Use atomic writes: write to `.tmp` file, then `os.rename()` (Req 11.1)
- Create data directory with permissions 0o755 (Req 11.6)
- Create JSON files with permissions 0o644 (Req 11.6)
- Validate date keys match ISO 8601 format (Req 11.2)
- Validate status values are "in-office" or "remote" (Req 11.3)
- Overwrite existing records for same date (Req 2.9)
- Pretty-print JSON with indent=2 (Req 2.10)
- Raise `StorageError` for I/O failures (Req 10.2, 11.4)

### Component: BusinessDayCalculator

**Purpose**: Compute business day counts and validate workdays
**Location**: `swiper/business_days.py`
**Implements**: Requirement 4 (all criteria)

#### Interface

```python
from datetime import date
from typing import List

class BusinessDayCalculator:
    """Calculates business days excluding weekends and holidays."""

    def __init__(self, exclusion_days: List[date]):
        """Initialize with holiday list."""
        pass

    def is_weekend(self, check_date: date) -> bool:
        """Check if date is Saturday or Sunday. Implements Req 4.1."""
        pass

    def is_exclusion_day(self, check_date: date) -> bool:
        """Check if date is a holiday. Implements Req 4.2."""
        pass

    def is_workday(self, check_date: date) -> bool:
        """Check if date is a workday. Implements Req 4.3."""
        pass

    def count_workdays(self, start_date: date, end_date: date) -> int:
        """Count workdays in date range (inclusive). Implements Req 4.4-4.6."""
        pass

    def get_exclusions_in_range(self, start_date: date, end_date: date) -> List[date]:
        """Get exclusion days within date range. Implements Req 4.7."""
        pass
```

#### Implementation Notes

- Weekend check: `date.weekday() in [5, 6]` (Saturday=5, Sunday=6) (Req 4.5)
- Workday definition: weekday AND not exclusion day (Req 4.3)
- Use set for O(1) exclusion day lookups
- Iterate date range using `timedelta(days=1)` for workday counting (Req 4.4)
- Only count exclusion days that are also weekdays (Monday-Friday) (Req 4.7)

### Component: ReportingPeriodCalculator

**Purpose**: Determine reporting periods and calculate effective required days
**Location**: `swiper/reporting.py`
**Implements**: Requirements 3, 5

#### Interface

```python
from datetime import date
from typing import List, Optional
from swiper.models import ReportingPeriod
from swiper.business_days import BusinessDayCalculator

class ReportingPeriodCalculator:
    """Manages reporting period calculations."""

    def __init__(
        self,
        periods: List[ReportingPeriod],
        business_day_calc: BusinessDayCalculator
    ):
        """Initialize with period definitions and business day calculator."""
        pass

    def get_period_for_date(self, check_date: date) -> ReportingPeriod:
        """Find reporting period containing date. Implements Req 3.1-3.3."""
        pass

    def get_current_period(self) -> ReportingPeriod:
        """Get reporting period for today. Implements Req 3.4."""
        pass

    def calculate_effective_required_days(self, period: ReportingPeriod) -> int:
        """Calculate effective required days for period. Implements Req 5.1-5.6."""
        pass

    def enrich_period_with_exclusions(self, period: ReportingPeriod) -> ReportingPeriod:
        """Add exclusion days and calculate effective required days. Implements Req 5.1-5.6."""
        pass

    def get_period_by_number(self, period_number: int) -> Optional[ReportingPeriod]:
        """Get reporting period by its number."""
        pass

    def get_all_periods(self) -> List[ReportingPeriod]:
        """Get all configured reporting periods."""
        pass
```

#### Implementation Notes

- Period matching: `start_date <= check_date <= end_date` (Req 3.3)
- Raise `ValidationError` if no period found (Req 3.2)
- Return `ReportingPeriod` dataclass with all fields (Req 3.5)
- Calculate effective required: `baseline - weekday_exclusion_count` (Req 5.4)
- Minimum effective required is 0 (Req 5.5)
- Use BusinessDayCalculator to filter exclusions in date range (Req 5.2, 5.3)
- Return enriched ReportingPeriod with exclusion_days and effective_required_days (Req 5.6)

### Component: ComplianceChecker

**Purpose**: Evaluate attendance compliance against requirements
**Location**: `swiper/compliance.py`
**Implements**: Requirements 6, 12

#### Interface

```python
from datetime import date
from swiper.models import ReportingPeriod, ComplianceStatus
from swiper.storage import AttendanceStore
from swiper.reporting import ReportingPeriodCalculator
from swiper.business_days import BusinessDayCalculator

class ComplianceChecker:
    """Evaluates attendance compliance."""

    def __init__(
        self,
        attendance_store: AttendanceStore,
        reporting_calc: ReportingPeriodCalculator,
        business_day_calc: BusinessDayCalculator
    ):
        """Initialize with required dependencies."""
        pass

    def check_compliance(self, period: ReportingPeriod, as_of_date: date = None) -> ComplianceStatus:
        """Evaluate compliance for reporting period. Implements Req 6.1-6.8, 12.1-12.6."""
        pass

    def _count_in_office_days(self, period: ReportingPeriod) -> int:
        """Count in-office days recorded in period. Implements Req 6.1-6.2."""
        pass

    def _calculate_remaining_workdays(self, period: ReportingPeriod, as_of_date: date) -> int:
        """Calculate workdays remaining from date through period end. Implements Req 6.7."""
        pass

    def _determine_compliance_risk(
        self,
        is_compliant: bool,
        days_short: int,
        workdays_remaining: int
    ) -> str:
        """Determine compliance risk level. Implements Req 12.1-12.6."""
        pass
```

#### Implementation Notes

- Count only "in-office" status records (Req 6.2)
- Retrieve effective_required_days from ReportingPeriodCalculator (Req 6.3)
- Compliant if `in_office_count >= effective_required_days` (Req 6.4)
- Calculate days_short: `max(0, effective_required - in_office_count)` (Req 6.5)
- Calculate days_ahead: `max(0, in_office_count - effective_required)` (Req 6.6)
- Use BusinessDayCalculator for remaining workdays (Req 6.7)
- Return ComplianceStatus dataclass (Req 6.8)
- **Risk levels** (Req 12.1-12.6):
  - "achieved": `is_compliant == True`
  - "impossible": `days_short > workdays_remaining`
  - "critical": `days_short == workdays_remaining` (not zero)
  - "at-risk": `days_short > 0.75 * workdays_remaining`
  - "possible": `days_short > 0 and days_short <= workdays_remaining`

### Component: CLIInterface

**Purpose**: Process user commands and render formatted output
**Location**: `swiper/cli.py`
**Implements**: Requirements 2 (criteria 2.1-2.5, 2.11), 7, 8, 9, 10 (all criteria), 12 (criteria 12.7-12.11)

#### Interface

```python
import click
from pathlib import Path
from datetime import date
from typing import Optional

@click.group()
@click.pass_context
def cli(ctx):
    """In-Office Attendance Tracking CLI. Implements Req 10.4."""
    pass

@cli.command()
@click.argument("status", type=click.Choice(["in-office", "remote"]))
@click.option("--date", type=str, help="Date in YYYY-MM-DD format (default: today)")
@click.pass_context
def record(ctx, status: str, date: Optional[str]):
    """Record attendance for a day. Implements Req 2.1-2.5, 2.11."""
    pass

@cli.command()
@click.pass_context
def status(ctx):
    """Show current reporting period compliance status. Implements Req 7.1-7.10."""
    pass

@cli.command()
@click.option("--period", type=int, help="Reporting period number")
@click.option("--all", "show_all", is_flag=True, help="Show all periods")
@click.pass_context
def report(ctx, period: Optional[int], show_all: bool):
    """Generate attendance report. Implements Req 8.1-8.7."""
    pass

@cli.group()
def config():
    """Configuration management commands. Implements Req 9.1-9.4."""
    pass

@config.command()
@click.pass_context
def show(ctx):
    """Show current configuration. Implements Req 9.1."""
    pass

@config.command()
@click.pass_context
def validate(ctx):
    """Validate configuration files. Implements Req 9.2-9.4."""
    pass

# Helper functions
def format_status_output(compliance: ComplianceStatus) -> str:
    """Format compliance status for display. Implements Req 7.3-7.10, 12.7-12.10."""
    pass

def format_report_output(period: ReportingPeriod, compliance: ComplianceStatus) -> str:
    """Format detailed report for display. Implements Req 8.5-8.6, 12.11."""
    pass

def handle_error(error: Exception) -> None:
    """Handle and display errors gracefully. Implements Req 10.1-10.3, 10.6-10.7."""
    pass
```

#### Implementation Notes

- Use Click decorators for command definition
- Validate date format using datetime.strptime() (Req 2.4)
- Check future dates: `parsed_date > date.today()` (Req 2.5)
- Display confirmation after successful record (Req 2.11)
- Show period details in readable format (Req 7.3-7.4)
- Display in-office count, required count, remaining (Req 7.5-7.7)
- Show compliance status with risk level (Req 7.8-7.10, 12.7)
- Display appropriate warning messages for each risk level (Req 12.8-12.10)
- Handle invalid period numbers gracefully (Req 8.4)
- Iterate all periods for --all flag (Req 8.7)
- Catch custom exceptions and display user-friendly messages (Req 10.1)
- Exit with code 0 on success, non-zero on error (Req 10.6-10.7)
- Show command help for invalid arguments (Req 10.5)

## Configuration File Formats

### config/config.toml
```toml
[policy]
required_days_per_period = 20  # Minimum in-office days per 13-week period
period_length_weeks = 13       # Length of reporting periods

[data]
reporting_periods_file = "config/reporting_periods.toml"
exclusion_days_file = "config/holidays.yaml"
attendance_data_dir = "data/"
```

### config/reporting_periods.toml
```toml
[[periods]]
period_number = 1
start_date = 2025-08-15
end_date = 2025-11-14
deadline = 2025-12-03

[[periods]]
period_number = 2
start_date = 2025-10-20
end_date = 2026-01-16
deadline = 2026-01-28

# ... additional periods
```

### config/holidays.yaml
```yaml
# business-python compatible format
working_days:
  - Monday
  - Tuesday
  - Wednesday
  - Thursday
  - Friday

holidays:
  - 2025-09-01  # Labor Day
  - 2025-10-13  # Indigenous People's Day
  - 2025-11-11  # Veteran's Day
  - 2025-11-24  # Thanksgiving week
  - 2025-11-25
  - 2025-11-26
  - 2025-11-27
  - 2025-11-28
  # ... additional holidays
```

### data/attendance_2025.json
```json
{
  "2025-08-15": "in-office",
  "2025-08-16": "remote",
  "2025-08-17": "in-office"
}
```

## Dependencies

### requirements.txt
```
click>=8.1.0
pydantic>=2.0.0
pyyaml>=6.0.0
tomli>=2.0.0; python_version < "3.11"
```

## Testing Strategy

Each component shall have corresponding unit tests:

- **test_config.py**: Test configuration loading, validation, and error handling
- **test_storage.py**: Test JSON read/write, atomic operations, data validation
- **test_business_days.py**: Test workday calculations with various scenarios
- **test_reporting.py**: Test period determination and effective days calculation
- **test_compliance.py**: Test compliance checks and risk level determination
- **test_cli.py**: Test command parsing, output formatting, error handling

Use pytest fixtures for sample data and temporary file systems.

---

**Detailed design complete.** All 6 components from the blueprint have been specified with interfaces, data models, configuration formats, and implementation guidance. Each component interface includes requirement references showing traceability.

**Proceed to generate implementation tasks?**
