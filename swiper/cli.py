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
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

from swiper.business_days import BusinessDayCalculator
from swiper.compliance import ComplianceChecker, ComplianceStatus
from swiper.config import ConfigurationManager
from swiper.exceptions import ConfigurationError, StorageError, ValidationError
from swiper.models import AttendanceRecord, ReportingPeriod
from swiper.reporting import ReportingPeriodCalculator
from swiper.storage import AttendanceStore

# Initialize rich console
console = Console()


def get_risk_color(risk_level: str) -> str:
    """Get color for risk level display."""
    colors = {
        "achieved": "green",
        "possible": "cyan",
        "at-risk": "yellow",
        "critical": "orange3",
        "impossible": "red",
    }
    return colors.get(risk_level, "white")


def get_risk_icon(risk_level: str) -> str:
    """Get icon for risk level display."""
    icons = {
        "achieved": "✓",
        "possible": "●",
        "at-risk": "⚠",
        "critical": "⚠⚠",
        "impossible": "✗",
    }
    return icons.get(risk_level, "")


def get_compliance_icon(is_compliant: bool) -> str:
    """Get icon for compliance status."""
    return "✓" if is_compliant else "✗"


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

        # Display success message with colors
        status_color = "green" if status == "in-office" else "cyan"
        icon = "🏢" if status == "in-office" else "🏠"
        console.print(
            f"[bold {status_color}]{icon} Recorded {status}[/] for [bold]{record_date}[/]"
        )

    except (ValidationError, StorageError) as e:
        console.print(f"[bold red]✗ Error:[/] {e}", style="red")
        sys.exit(1)


def format_status_output(period: ReportingPeriod, compliance: ComplianceStatus) -> None:
    """Format and display compliance status with rich formatting.

    Args:
        period: The reporting period
        compliance: The compliance status
    """
    # Create title
    title = f"📊 Reporting Period {period.period_number}"

    # Create info table
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column("Label", style="cyan", width=30)
    table.add_column("Value", style="white")

    # Period info
    table.add_row("Period", f"{period.start_date} to {period.end_date}")
    table.add_row("Report Due", str(period.report_date))
    table.add_section()

    # Requirements
    table.add_row("Required Days (Baseline)", str(period.baseline_required_days))
    exclusion_info = f"{compliance.effective_required_days} (after {len(period.exclusion_days)} exclusions)"
    table.add_row("Required Days (Effective)", exclusion_info)
    table.add_section()

    # Progress
    table.add_row("In-Office Days Recorded", f"[bold green]{compliance.in_office_days}[/]")
    table.add_row("Remaining Required Days", f"[bold yellow]{compliance.remaining_required_days}[/]")
    table.add_row("Workdays Remaining", f"[bold cyan]{compliance.remaining_workdays}[/]")
    table.add_section()

    # Compliance status
    icon = get_compliance_icon(compliance.is_compliant)
    status_color = "green" if compliance.is_compliant else "red"
    status_text = "COMPLIANT" if compliance.is_compliant else "NOT COMPLIANT"
    table.add_row("Status", f"[bold {status_color}]{icon} {status_text}[/]")

    # Risk level
    risk_icon = get_risk_icon(compliance.risk_level)
    risk_color = get_risk_color(compliance.risk_level)
    table.add_row("Risk Level", f"[bold {risk_color}]{risk_icon} {compliance.risk_level.upper()}[/]")

    # Display table
    panel = Panel(table, title=title, border_style="blue")
    console.print()
    console.print(panel)

    # Display warnings based on risk level
    if compliance.risk_level == "impossible":
        short_by = compliance.remaining_required_days - compliance.remaining_workdays
        console.print()
        console.print(
            Panel(
                f"⛔ Compliance cannot be achieved. Short by [bold]{short_by}[/] days with only [bold]{compliance.remaining_workdays}[/] workdays remaining.",
                title="WARNING",
                border_style="red",
                padding=(0, 1)
            )
        )
    elif compliance.risk_level == "critical":
        console.print()
        console.print(
            Panel(
                f"You must be in-office for [bold]all {compliance.remaining_workdays} remaining workdays[/] to achieve compliance.",
                title="⚠ CRITICAL",
                border_style="orange3",
                padding=(0, 1)
            )
        )
    elif compliance.risk_level == "at-risk":
        required_pct = (
            (compliance.remaining_required_days / compliance.remaining_workdays * 100)
            if compliance.remaining_workdays > 0
            else 0
        )
        console.print()
        console.print(
            Panel(
                f"You need [bold]{compliance.remaining_required_days}[/] more in-office days out of [bold]{compliance.remaining_workdays}[/] remaining workdays ([bold]{required_pct:.0f}%[/] attendance required).",
                title="⚠ AT RISK",
                border_style="yellow",
                padding=(0, 1)
            )
        )
    console.print()


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

        format_status_output(current_period, compliance)

    except (ValidationError, StorageError) as e:
        console.print(f"[bold red]✗ Error:[/] {e}", style="red")
        sys.exit(1)


def format_report_output(
    period: ReportingPeriod, compliance: ComplianceStatus, show_header: bool = True
) -> None:
    """Format and display a compliance report for a single period.

    Args:
        period: The reporting period
        compliance: The compliance status
        show_header: Whether to show a header with period details
    """
    # Create title
    title = f"📊 Reporting Period {period.period_number}" if show_header else "📊 Current Period"

    # Create info table
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Label", style="cyan", width=25)
    table.add_column("Value", style="white")

    # Period info
    table.add_row("Period", f"{period.start_date} to {period.end_date}")
    table.add_row("Report Due", str(period.report_date))
    table.add_row(
        "Required Days",
        f"{period.baseline_required_days} baseline, "
        f"{compliance.effective_required_days} effective "
        f"({len(period.exclusion_days)} exclusions)"
    )
    table.add_row("", "")  # Empty row for spacing

    # Progress
    table.add_row("Days Completed", f"[bold green]{compliance.in_office_days}[/]")
    table.add_row("Remaining Required", f"[bold yellow]{compliance.remaining_required_days}[/]")
    table.add_row("Remaining Workdays", f"[bold cyan]{compliance.remaining_workdays}[/]")
    table.add_row("", "")  # Empty row for spacing

    # Compliance status
    icon = get_compliance_icon(compliance.is_compliant)
    status_color = "green" if compliance.is_compliant else "red"
    status_text = "COMPLIANT" if compliance.is_compliant else "NOT COMPLIANT"
    table.add_row("Status", f"[bold {status_color}]{icon} {status_text}[/]")

    # Risk level
    risk_icon = get_risk_icon(compliance.risk_level)
    risk_color = get_risk_color(compliance.risk_level)
    table.add_row("Risk Level", f"[bold {risk_color}]{risk_icon} {compliance.risk_level.upper()}[/]")

    # Display table
    console.print()
    console.print(Panel(table, title=title, border_style="blue"))

    # Display warnings based on risk level
    if compliance.risk_level == "impossible":
        short_by = compliance.remaining_required_days - compliance.remaining_workdays
        console.print(
            Panel(
                f"⛔ Compliance cannot be achieved. Short by [bold]{short_by}[/] days.",
                title="WARNING",
                border_style="red",
                padding=(0, 1)
            )
        )
    elif compliance.risk_level == "critical":
        console.print(
            Panel(
                f"You must be in-office for [bold]all {compliance.remaining_workdays} remaining workdays[/] to achieve compliance.",
                title="⚠ CRITICAL",
                border_style="orange3",
                padding=(0, 1)
            )
        )
    elif compliance.risk_level == "at-risk":
        required_pct = (
            (compliance.remaining_required_days / compliance.remaining_workdays * 100)
            if compliance.remaining_workdays > 0
            else 0
        )
        console.print(
            Panel(
                f"You need [bold]{compliance.remaining_required_days}[/] more days ([bold]{required_pct:.0f}%[/] of remaining workdays).",
                title="⚠ AT RISK",
                border_style="yellow",
                padding=(0, 1)
            )
        )
    console.print()


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
                console.print(f"[bold red]✗ Error:[/] Invalid period number: {period}", style="red")
                sys.exit(1)
            periods = [period_obj]
        else:
            # Default to current period
            periods = [app.reporting_calc.get_current_period()]

        # Generate and display reports
        for p in periods:
            compliance = app.compliance_checker.calculate_compliance_status(
                p, as_of_date=date.today()
            )
            # Show header if reporting on multiple periods OR if a specific period was requested
            show_period_header = show_all or period is not None
            format_report_output(p, compliance, show_header=show_period_header)

    except (ValidationError, StorageError) as e:
        console.print(f"[bold red]✗ Error:[/] {e}", style="red")
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

        # Create configuration table
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=30)
        table.add_column("Value", style="white")

        # Policy settings
        table.add_row(
            "[bold]Policy Settings[/]",
            ""
        )
        table.add_row(
            "  Required Days Per Period",
            str(settings.policy.required_days_per_period)
        )
        table.add_row("", "")  # Empty row for spacing

        # Data settings
        table.add_row("[bold]Data Settings[/]", "")
        table.add_row("  Reporting Periods File", settings.data.reporting_periods_file)
        table.add_row("  Exclusion Days File", settings.data.exclusion_days_file)
        table.add_row("  Attendance Data Dir", settings.data.attendance_data_dir)

        # Display table
        console.print()
        console.print(Panel(table, title="⚙️  Configuration Settings", border_style="blue"))
        console.print()

    except (ConfigurationError, ValidationError) as e:
        console.print(f"[bold red]✗ Error:[/] {e}", style="red")
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

        # Create validation results table
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Item", style="cyan", width=25)
        table.add_column("Count", style="green")

        table.add_row("Reporting Periods", str(len(periods)))
        table.add_row("Exclusion Days", str(len(exclusions)))

        console.print()
        console.print(
            Panel(
                table,
                title="✓ Configuration Valid",
                border_style="green",
                subtitle="All configuration files are properly formatted"
            )
        )
        console.print()

    except (ConfigurationError, ValidationError) as e:
        console.print(f"[bold red]✗ Error:[/] {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    cli()
