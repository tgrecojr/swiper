"""
CLI interface for the Swiper attendance tracking application.

This module provides Click-based commands for recording attendance,
checking compliance status, and generating reports.
"""

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click

from swiper.business_days import BusinessDayCalculator
from swiper.compliance import ComplianceChecker, ComplianceStatus
from swiper.config import ConfigurationManager
from swiper.exceptions import ConfigurationError, StorageError, ValidationError
from swiper.models import AttendanceRecord, ReportingPeriod
from swiper.reporting import ReportingPeriodCalculator
from swiper.storage import AttendanceStore


class AppContext:
    """Context object to share configuration and components across CLI commands."""

    def __init__(self, config_path: Path):
        """Initialize application context with configuration."""
        self.config_manager = ConfigurationManager(config_path)
        self.config_manager.validate_all()

        # Initialize components
        settings = self.config_manager.get_settings()
        exclusion_days = self.config_manager.get_exclusion_days()
        reporting_periods = self.config_manager.get_reporting_periods()

        self.business_day_calc = BusinessDayCalculator(exclusion_days)
        self.attendance_store = AttendanceStore(Path(settings.data.attendance_data_dir))
        self.reporting_calc = ReportingPeriodCalculator(
            reporting_periods, self.business_day_calc
        )
        self.compliance_checker = ComplianceChecker(
            self.reporting_calc, self.business_day_calc, self.attendance_store
        )


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/config.toml"),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, config: Path) -> None:
    """Swiper - In-Office Attendance Tracking Application.

    Track your in-office attendance and monitor compliance with
    your organization's return-to-office policy.
    """
    try:
        ctx.obj = AppContext(config)
    except (ConfigurationError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("status", type=click.Choice(["in-office", "remote"]))
@click.option(
    "--date",
    "date_str",
    type=str,
    default=None,
    help="Date to record (YYYY-MM-DD format). Defaults to today.",
)
@click.pass_obj
def record(app: AppContext, status: str, date_str: Optional[str]) -> None:
    """Record attendance for a specific date.

    STATUS must be either 'in-office' or 'remote'.

    Examples:
        swiper record in-office
        swiper record remote --date 2025-01-15
    """
    try:
        # Parse date
        if date_str:
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError(
                    f"Invalid date format: {date_str}. Use YYYY-MM-DD format."
                )
        else:
            record_date = date.today()

        # Validate date is not in the future
        if record_date > date.today():
            raise ValidationError("Cannot record attendance for future dates")

        # Create and save record
        attendance_record = AttendanceRecord(date=record_date, status=status)
        app.attendance_store.save_record(attendance_record)

        click.echo(f"Recorded {status} for {record_date}")

    except (ValidationError, StorageError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def format_status_output(period: ReportingPeriod, compliance: ComplianceStatus) -> str:
    """Format compliance status for display.

    Args:
        period: The reporting period
        compliance: The compliance status

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append(f"Reporting Period {period.period_number}")
    lines.append(f"Period: {period.start_date} to {period.end_date}")
    lines.append(f"Report Due: {period.report_date}")
    lines.append("")
    lines.append(f"Required Days (Baseline): {period.baseline_required_days}")
    lines.append(
        f"Required Days (Effective): {compliance.effective_required_days} (after {len(period.exclusion_days)} exclusions)"
    )
    lines.append(f"In-Office Days Recorded: {compliance.in_office_days}")
    lines.append(f"Remaining Required Days: {compliance.remaining_required_days}")
    lines.append(f"Workdays Remaining: {compliance.remaining_workdays}")
    lines.append("")

    # Compliance status
    if compliance.is_compliant:
        lines.append("Status: ✓ COMPLIANT")
    else:
        lines.append("Status: ✗ NOT COMPLIANT")

    # Risk level with appropriate warnings
    lines.append(f"Risk Level: {compliance.risk_level.upper()}")

    if compliance.risk_level == "impossible":
        short_by = compliance.remaining_required_days - compliance.remaining_workdays
        lines.append("")
        lines.append(
            f"WARNING: Compliance cannot be achieved. Short by {short_by} days "
            f"with only {compliance.remaining_workdays} workdays remaining."
        )
    elif compliance.risk_level == "critical":
        lines.append("")
        lines.append(
            f"CRITICAL: You must be in-office for all {compliance.remaining_workdays} "
            "remaining workdays to achieve compliance."
        )
    elif compliance.risk_level == "at-risk":
        buffer_days = compliance.remaining_workdays - compliance.remaining_required_days
        required_pct = (
            (compliance.remaining_required_days / compliance.remaining_workdays * 100)
            if compliance.remaining_workdays > 0
            else 0
        )
        lines.append("")
        lines.append(
            f"AT RISK: You need {compliance.remaining_required_days} more in-office days "
            f"out of {compliance.remaining_workdays} remaining workdays "
            f"({required_pct:.0f}% attendance required)."
        )

    return "\n".join(lines)


@cli.command()
@click.pass_obj
def status(app: AppContext) -> None:
    """Show current compliance status.

    Displays your attendance status for the current reporting period,
    including days completed, days remaining, and compliance risk level.

    Example:
        swiper status
    """
    try:
        current_period = app.reporting_calc.get_current_period()
        compliance = app.compliance_checker.calculate_compliance_status(
            current_period, as_of_date=date.today()
        )

        output = format_status_output(current_period, compliance)
        click.echo(output)

    except (ValidationError, StorageError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def format_report_output(
    period: ReportingPeriod, compliance: ComplianceStatus, show_header: bool = True
) -> str:
    """Format a compliance report for a single period.

    Args:
        period: The reporting period
        compliance: The compliance status
        show_header: Whether to show a header with period details

    Returns:
        Formatted string for display
    """
    lines = []

    if show_header:
        lines.append("=" * 70)
        lines.append(f"REPORTING PERIOD {period.period_number}")
        lines.append("=" * 70)

    lines.append(f"Period: {period.start_date} to {period.end_date}")
    lines.append(f"Report Due: {period.report_date}")
    lines.append(
        f"Required Days: {period.baseline_required_days} baseline, "
        f"{compliance.effective_required_days} effective "
        f"({len(period.exclusion_days)} exclusions)"
    )
    lines.append("")
    lines.append(f"Days Completed: {compliance.in_office_days}")
    lines.append(f"Remaining Required: {compliance.remaining_required_days}")
    lines.append(f"Remaining Workdays: {compliance.remaining_workdays}")
    lines.append("")

    # Compliance status
    status_symbol = "✓" if compliance.is_compliant else "✗"
    status_text = "COMPLIANT" if compliance.is_compliant else "NOT COMPLIANT"
    lines.append(f"Status: {status_symbol} {status_text}")
    lines.append(f"Risk Level: {compliance.risk_level.upper()}")

    # Add warnings based on risk level
    if compliance.risk_level == "impossible":
        short_by = compliance.remaining_required_days - compliance.remaining_workdays
        lines.append("")
        lines.append(
            f"WARNING: Compliance cannot be achieved. Short by {short_by} days."
        )
    elif compliance.risk_level == "critical":
        lines.append("")
        lines.append(
            f"CRITICAL: Must be in-office for all {compliance.remaining_workdays} remaining workdays."
        )
    elif compliance.risk_level == "at-risk":
        required_pct = (
            (compliance.remaining_required_days / compliance.remaining_workdays * 100)
            if compliance.remaining_workdays > 0
            else 0
        )
        lines.append("")
        lines.append(
            f"AT RISK: Need {compliance.remaining_required_days} more days "
            f"({required_pct:.0f}% of remaining workdays)."
        )

    return "\n".join(lines)


@cli.command()
@click.option(
    "--period",
    type=int,
    default=None,
    help="Report on a specific period number",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Report on all periods",
)
@click.pass_obj
def report(app: AppContext, period: Optional[int], show_all: bool) -> None:
    """Generate compliance reports.

    By default, shows the current period. Use --period to specify a
    different period, or --all to show all periods.

    Examples:
        swiper report
        swiper report --period 5
        swiper report --all
    """
    try:
        # Determine which periods to report on
        if show_all:
            periods = app.reporting_calc.get_all_periods()
        elif period is not None:
            period_obj = app.reporting_calc.get_period_by_number(period)
            if period_obj is None:
                click.echo(f"Error: Invalid period number: {period}", err=True)
                sys.exit(1)
            periods = [period_obj]
        else:
            # Default to current period
            periods = [app.reporting_calc.get_current_period()]

        # Generate reports
        outputs = []
        for p in periods:
            compliance = app.compliance_checker.calculate_compliance_status(
                p, as_of_date=date.today()
            )
            # Show header if reporting on multiple periods OR if a specific period was requested
            show_period_header = show_all or period is not None
            output = format_report_output(p, compliance, show_header=show_period_header)
            outputs.append(output)

        # Display with separators for multiple periods
        if show_all:
            click.echo("\n\n".join(outputs))
        else:
            click.echo(outputs[0])

    except (ValidationError, StorageError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def config() -> None:
    """Configuration management commands.

    Commands for viewing and validating configuration files.
    """
    pass


@config.command("show")
@click.pass_obj
def config_show(app: AppContext) -> None:
    """Show current configuration settings.

    Displays all configuration settings including policy requirements
    and data file paths.

    Example:
        swiper config show
    """
    try:
        settings = app.config_manager.get_settings()

        lines = []
        lines.append("Configuration Settings")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Policy Settings:")
        lines.append(
            f"  Required Days Per Period: {settings.policy.required_days_per_period}"
        )
        lines.append("")
        lines.append("Data Settings:")
        lines.append(f"  Reporting Periods File: {settings.data.reporting_periods_file}")
        lines.append(f"  Exclusion Days File: {settings.data.exclusion_days_file}")
        lines.append(f"  Attendance Data Dir: {settings.data.attendance_data_dir}")

        click.echo("\n".join(lines))

    except (ConfigurationError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@config.command("validate")
@click.pass_obj
def config_validate(app: AppContext) -> None:
    """Validate all configuration files.

    Checks that all configuration files are properly formatted and
    contain valid data.

    Example:
        swiper config validate
    """
    try:
        # Configuration is already validated in AppContext initialization
        # Get counts for display
        periods = app.config_manager.get_reporting_periods()
        exclusions = app.config_manager.get_exclusion_days()

        lines = []
        lines.append("Configuration valid ✓")
        lines.append(f"  Reporting Periods: {len(periods)}")
        lines.append(f"  Exclusion Days: {len(exclusions)}")

        click.echo("\n".join(lines))

    except (ConfigurationError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
