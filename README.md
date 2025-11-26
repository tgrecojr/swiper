# Swiper - In-Office Attendance Tracking

A command-line application for tracking in-office attendance and monitoring compliance with return-to-office policies.

## Overview

Swiper helps you track when you work in-office versus remotely and automatically calculates whether you're meeting your organization's return-to-office requirements. It accounts for holidays, provides risk assessments, and generates compliance reports.

### Key Features

- **Flexible Attendance Recording**: Track in-office and remote work days
- **Automated Compliance Checking**: Know if you're on track to meet requirements
- **Risk Assessment**: Get early warnings if you're at risk of non-compliance
- **Holiday Awareness**: Automatically excludes holidays from requirements
- **Multiple Reporting Periods**: Supports overlapping periods with different deadlines
- **Data Persistence**: Stores attendance records in human-readable JSON files

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)

### Install in Development Mode

```bash
# Clone the repository
git clone https://github.com/tgrecojr/swiper.git
cd swiper

# Install in development mode
pip install -e .
```

### Install for Production

```bash
pip install swiper
```

## Quick Start

### 1. Configure Your Settings

The application comes with default configuration files in the `config/` directory:

- `config.toml` - Main configuration (policy settings, file paths)
- `reporting_periods.toml` - Reporting period definitions
- `holidays.yaml` - Holiday calendar

Copy `config/config.example.toml` to `config/config.toml` and customize as needed.

### 2. Record Your Attendance

Record today's attendance:

```bash
swiper record in-office
swiper record remote
```

Record historical attendance:

```bash
swiper record in-office --date 2025-08-20
swiper record remote --date 2025-08-21
```

### 3. Check Your Status

View your current compliance status:

```bash
swiper status
```

Example output:

```
Reporting Period 1
Period: 2025-08-15 to 2025-11-14
Report Due: 2025-12-03

Required Days (Baseline): 20
Required Days (Effective): 18 (after 2 exclusions)
In-Office Days Recorded: 12
Remaining Required Days: 6
Workdays Remaining: 35

Status: ✗ NOT COMPLIANT
Risk Level: POSSIBLE
```

### 4. Generate Reports

Report on current period:

```bash
swiper report
```

Report on a specific period:

```bash
swiper report --period 3
```

Report on all periods:

```bash
swiper report --all
```

## CLI Commands

### `swiper record`

Record attendance for a specific date.

**Usage:**
```bash
swiper record {in-office|remote} [--date YYYY-MM-DD]
```

**Options:**
- `--date`: Date to record (defaults to today)

**Examples:**
```bash
swiper record in-office
swiper record remote --date 2025-08-15
```

### `swiper status`

Show current compliance status including risk assessment.

**Usage:**
```bash
swiper status
```

Shows:
- Current reporting period details
- Required days (baseline and effective)
- Days recorded and remaining
- Compliance status
- Risk level with warnings

### `swiper report`

Generate compliance reports for one or more periods.

**Usage:**
```bash
swiper report [--period N] [--all]
```

**Options:**
- `--period N`: Report on specific period number
- `--all`: Report on all configured periods

**Examples:**
```bash
swiper report              # Current period
swiper report --period 5   # Specific period
swiper report --all        # All periods
```

### `swiper config`

Configuration management commands.

**Usage:**
```bash
swiper config {show|validate}
```

**Subcommands:**
- `show`: Display current configuration settings
- `validate`: Validate all configuration files

**Examples:**
```bash
swiper config show
swiper config validate
```

## Configuration

### Main Configuration (`config/config.toml`)

```toml
[policy]
# Number of required in-office days per reporting period
required_days_per_period = 20

[data]
# Paths to configuration and data files
reporting_periods_file = "config/reporting_periods.toml"
exclusion_days_file = "config/holidays.yaml"
attendance_data_dir = "data"
```

### Reporting Periods (`config/reporting_periods.toml`)

Define your organization's reporting periods:

```toml
[[periods]]
period_number = 1
start_date = "2025-08-15"
end_date = "2025-11-14"
report_date = "2025-12-03"
```

**Fields:**
- `period_number`: Unique identifier (integer > 0)
- `start_date`: First day of the period (YYYY-MM-DD)
- `end_date`: Last day of the period (YYYY-MM-DD)
- `report_date`: Deadline for compliance reporting (YYYY-MM-DD)

### Holiday Calendar (`config/holidays.yaml`)

Define holidays and company closures:

```yaml
holidays:
  - 2025-09-01  # Labor Day
  - 2025-11-27  # Thanksgiving
  - 2025-12-25  # Christmas
```

Holidays that fall on weekdays automatically reduce the required in-office days for that period.

## Risk Levels

Swiper calculates risk levels to help you stay on track:

| Risk Level | Meaning | Description |
|------------|---------|-------------|
| **ACHIEVED** | ✅ Compliant | You've met the requirement |
| **POSSIBLE** | 🟢 Low Risk | Plenty of buffer days remaining |
| **AT-RISK** | 🟡 Medium Risk | Need >75% attendance for remaining days |
| **CRITICAL** | 🟠 High Risk | Must be in-office every remaining workday |
| **IMPOSSIBLE** | 🔴 Cannot Achieve | Not enough workdays left to meet requirement |

## Data Storage

Attendance records are stored in JSON files organized by year:

```
data/
  attendance_2025.json
  attendance_2026.json
```

Each file contains records in a simple, human-readable format:

```json
{
  "2025-08-15": {"date": "2025-08-15", "status": "in-office"},
  "2025-08-16": {"date": "2025-08-16", "status": "remote"}
}
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=swiper --cov-report=term-missing

# Run specific test file
pytest tests/test_cli.py
```

### Test Coverage

The project maintains comprehensive test coverage:

- **156 tests** covering all components
- Business day calculator: 30 tests
- Configuration manager: 19 tests
- Attendance store: 22 tests
- Reporting period calculator: 28 tests
- Compliance checker: 29 tests
- CLI interface: 29 tests

### Project Structure

```
swiper/
├── swiper/               # Main package
│   ├── __init__.py
│   ├── __main__.py      # CLI entry point
│   ├── cli.py           # CLI implementation
│   ├── models.py        # Data models
│   ├── exceptions.py    # Custom exceptions
│   ├── config.py        # Configuration manager
│   ├── business_days.py # Business day calculator
│   ├── storage.py       # Attendance store
│   ├── reporting.py     # Reporting period calculator
│   └── compliance.py    # Compliance checker
├── tests/               # Test suite
├── config/              # Configuration files
├── data/                # Attendance data (gitignored)
└── docs/                # Documentation
```

## Troubleshooting

### Command not found: swiper

If you installed in development mode with `pip install -e .`:

```bash
# Use Python module syntax
python -m swiper --help
```

Or ensure your Python scripts directory is in your PATH.

### Configuration file not found

Swiper looks for configuration files relative to your current directory. Make sure you run commands from the project root:

```bash
cd /path/to/swiper
swiper status
```

Or specify the config path:

```bash
swiper --config /path/to/config.toml status
```

### No reporting period defined for current date

This means today's date falls outside all configured reporting periods. Update `config/reporting_periods.toml` to include periods covering the current date.

### Date validation errors

- Cannot record future dates - you can only record attendance for today or past dates
- Date format must be YYYY-MM-DD (e.g., 2025-08-15)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Support

For issues, questions, or suggestions:

- GitHub Issues: https://github.com/tgrecojr/swiper/issues
- Email: tgrecojr@gmail.com

## Acknowledgments

Built with:
- [Click](https://click.palletsprojects.com/) - Command-line interface framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [PyYAML](https://pyyaml.org/) - YAML parsing
