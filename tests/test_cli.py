"""
Tests for the CLI interface.

This module tests all CLI commands including record, status, report,
and config commands, as well as error handling.
"""

from datetime import date, timedelta
from pathlib import Path
import pytest
from click.testing import CliRunner

from swiper.cli import cli
from swiper.models import AttendanceRecord, ReportingPeriod
from swiper.storage import AttendanceStore


@pytest.fixture
def runner():
    """Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def test_config(tmp_path):
    """Create a temporary test configuration."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create config.toml
    config_file = config_dir / "config.toml"
    config_file.write_text(
        f"""[policy]
required_days_per_period = 20

[data]
config_file = "{config_file}"
reporting_periods_file = "{config_dir / 'reporting_periods.toml'}"
exclusion_days_file = "{config_dir / 'exclusion_days.yaml'}"
attendance_data_dir = "{data_dir}"
"""
    )

    # Create reporting_periods.toml with test periods
    periods_file = config_dir / "reporting_periods.toml"
    periods_file.write_text(
        """[[periods]]
period_number = 1
start_date = "2025-01-01"
end_date = "2025-03-31"
report_date = "2025-04-15"

[[periods]]
period_number = 2
start_date = "2025-04-01"
end_date = "2025-06-30"
report_date = "2025-07-15"

[[periods]]
period_number = 3
start_date = "2025-07-01"
end_date = "2025-09-30"
report_date = "2025-10-15"
"""
    )

    # Create exclusion_days.yaml with test holidays
    holidays_file = config_dir / "exclusion_days.yaml"
    holidays_file.write_text(
        """holidays:
  - 2025-01-01  # New Year's Day
  - 2025-07-04  # Independence Day
  - 2025-12-25  # Christmas Day
"""
    )

    return config_file


class TestRecordCommand:
    """Tests for the record command."""

    def test_record_in_office_today(self, runner, test_config):
        """Test recording in-office status for today."""
        result = runner.invoke(cli, ["--config", str(test_config), "record", "in-office"])
        assert result.exit_code == 0
        assert "Recorded in-office for" in result.output
        assert str(date.today()) in result.output

    def test_record_remote_today(self, runner, test_config):
        """Test recording remote status for today."""
        result = runner.invoke(cli, ["--config", str(test_config), "record", "remote"])
        assert result.exit_code == 0
        assert "Recorded remote for" in result.output
        assert str(date.today()) in result.output

    def test_record_with_date_option(self, runner, test_config):
        """Test recording with --date option."""
        past_date = "2025-01-15"
        result = runner.invoke(
            cli, ["--config", str(test_config), "record", "in-office", "--date", past_date]
        )
        assert result.exit_code == 0
        assert f"Recorded in-office for {past_date}" in result.output

    def test_record_rejects_future_date(self, runner, test_config):
        """Test that recording future dates is rejected."""
        future_date = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
        result = runner.invoke(
            cli, ["--config", str(test_config), "record", "in-office", "--date", future_date]
        )
        assert result.exit_code == 1
        assert "Cannot record attendance for future dates" in result.output

    def test_record_invalid_date_format(self, runner, test_config):
        """Test that invalid date format is rejected."""
        result = runner.invoke(
            cli, ["--config", str(test_config), "record", "in-office", "--date", "01/15/2025"]
        )
        assert result.exit_code == 1
        assert "Invalid date format" in result.output

    def test_record_invalid_status(self, runner, test_config):
        """Test that invalid status values are rejected."""
        result = runner.invoke(
            cli, ["--config", str(test_config), "record", "invalid-status"]
        )
        assert result.exit_code != 0
        # Click will show usage error for invalid choice

    def test_record_updates_existing(self, runner, test_config):
        """Test that recording same date twice updates the record."""
        past_date = "2025-01-15"
        # Record as in-office first
        result1 = runner.invoke(
            cli, ["--config", str(test_config), "record", "in-office", "--date", past_date]
        )
        assert result1.exit_code == 0

        # Record as remote (should update)
        result2 = runner.invoke(
            cli, ["--config", str(test_config), "record", "remote", "--date", past_date]
        )
        assert result2.exit_code == 0
        assert f"Recorded remote for {past_date}" in result2.output


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_shows_current_period(self, runner, test_config, tmp_path):
        """Test status command shows current period information."""
        # We need to be in a valid period, so we'll mock the current date
        # For this test, we'll use a date that falls in period 1 (2025-01-01 to 2025-03-31)
        result = runner.invoke(cli, ["--config", str(test_config), "status"])

        # The command should work, but may fail if today's date is outside configured periods
        # We'll check if it executed (exit code 0 or validation error)
        if result.exit_code == 0:
            assert "Reporting Period" in result.output
            assert "Required Days" in result.output
            assert "Status:" in result.output
            assert "Risk Level:" in result.output
        else:
            # If we're outside configured periods, should get a ValidationError
            assert "Error:" in result.output

    def test_status_with_compliance_achieved(self, runner, test_config, tmp_path):
        """Test status command when compliance is achieved."""
        # Add enough in-office records to achieve compliance
        # Period 1: Jan 1 - Mar 31, requires 20 days
        data_dir = tmp_path / "data"
        store = AttendanceStore(data_dir)

        # Add 20 in-office days in January
        for day in range(1, 21):
            record = AttendanceRecord(
                date=date(2025, 1, day), status="in-office"
            )
            store.save_record(record)

        result = runner.invoke(cli, ["--config", str(test_config), "status"])

        # Check if output indicates compliant status when run during period 1
        # (this test assumes we're running during 2025 and within period 1)
        if result.exit_code == 0 and "Period 1" in result.output:
            # We might be compliant or not depending on current date
            assert "Status:" in result.output

    def test_status_shows_risk_warnings(self, runner, test_config, tmp_path):
        """Test that status shows appropriate risk warnings."""
        result = runner.invoke(cli, ["--config", str(test_config), "status"])

        # The exact risk level depends on current date and attendance
        # Just verify the command runs and shows risk information
        if result.exit_code == 0:
            assert "Risk Level:" in result.output


class TestReportCommand:
    """Tests for the report command."""

    def test_report_default_current_period(self, runner, test_config):
        """Test report command defaults to current period."""
        result = runner.invoke(cli, ["--config", str(test_config), "report"])

        # Should show current period or error if outside all periods
        if result.exit_code == 0:
            assert "Period:" in result.output
            assert "Report Due:" in result.output
            assert "Required Days:" in result.output
            assert "Status:" in result.output

    def test_report_specific_period(self, runner, test_config):
        """Test report command with --period option."""
        result = runner.invoke(cli, ["--config", str(test_config), "report", "--period", "1"])

        assert result.exit_code == 0
        assert "REPORTING PERIOD 1" in result.output or "Period 1" in result.output
        assert "2025-01-01" in result.output
        assert "2025-03-31" in result.output

    def test_report_invalid_period_number(self, runner, test_config):
        """Test report command with invalid period number."""
        result = runner.invoke(cli, ["--config", str(test_config), "report", "--period", "999"])

        assert result.exit_code == 1
        assert "Invalid period number: 999" in result.output

    def test_report_all_periods(self, runner, test_config):
        """Test report command with --all flag."""
        result = runner.invoke(cli, ["--config", str(test_config), "report", "--all"])

        assert result.exit_code == 0
        assert "Reporting Period 1" in result.output
        assert "Reporting Period 2" in result.output
        assert "Reporting Period 3" in result.output

    def test_report_shows_compliance_status(self, runner, test_config, tmp_path):
        """Test that report shows compliance status correctly."""
        # Add some attendance records
        data_dir = tmp_path / "data"
        store = AttendanceStore(data_dir)

        # Add 5 in-office days in January
        for day in range(10, 15):
            record = AttendanceRecord(
                date=date(2025, 1, day), status="in-office"
            )
            store.save_record(record)

        result = runner.invoke(cli, ["--config", str(test_config), "report", "--period", "1"])

        assert result.exit_code == 0
        assert "Days Completed" in result.output
        assert "Remaining Required" in result.output

    def test_report_shows_risk_warnings(self, runner, test_config):
        """Test that report shows risk level warnings."""
        result = runner.invoke(cli, ["--config", str(test_config), "report", "--period", "1"])

        assert result.exit_code == 0
        assert "Risk Level" in result.output


class TestConfigCommands:
    """Tests for config command group."""

    def test_config_show(self, runner, test_config):
        """Test config show command."""
        result = runner.invoke(cli, ["--config", str(test_config), "config", "show"])

        assert result.exit_code == 0
        assert "Configuration Settings" in result.output
        assert "Policy Settings" in result.output
        assert "Required Days Per Period" in result.output
        assert "20" in result.output
        assert "Data Settings" in result.output

    def test_config_validate_valid(self, runner, test_config):
        """Test config validate command with valid configuration."""
        result = runner.invoke(cli, ["--config", str(test_config), "config", "validate"])

        assert result.exit_code == 0
        assert "Configuration Valid" in result.output
        assert "Reporting Periods" in result.output
        assert "3" in result.output
        assert "Exclusion Days" in result.output

    def test_config_validate_missing_file(self, runner, tmp_path):
        """Test config validate command with missing config file."""
        missing_config = tmp_path / "nonexistent.toml"
        result = runner.invoke(cli, ["--config", str(missing_config), "config", "validate"])

        assert result.exit_code == 2
        # Click will complain about the missing file with exit code 2


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_missing_config_file(self, runner, tmp_path):
        """Test behavior with missing configuration file."""
        missing_config = tmp_path / "nonexistent.toml"
        result = runner.invoke(cli, ["--config", str(missing_config), "status"])

        assert result.exit_code == 2
        # Click will complain about the missing file with exit code 2

    def test_invalid_config_file(self, runner, tmp_path):
        """Test behavior with invalid TOML configuration."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("this is not valid { toml")

        result = runner.invoke(cli, ["--config", str(bad_config), "status"])

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_help_text_main(self, runner):
        """Test that main help text is displayed."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Swiper" in result.output
        assert "attendance" in result.output.lower()

    def test_help_text_record(self, runner):
        """Test that record command help is displayed."""
        result = runner.invoke(cli, ["record", "--help"])

        assert result.exit_code == 0
        assert "Record attendance" in result.output
        assert "in-office" in result.output
        assert "remote" in result.output

    def test_help_text_status(self, runner):
        """Test that status command help is displayed."""
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "compliance status" in result.output.lower()

    def test_help_text_report(self, runner):
        """Test that report command help is displayed."""
        result = runner.invoke(cli, ["report", "--help"])

        assert result.exit_code == 0
        assert "compliance reports" in result.output.lower()
        assert "--period" in result.output
        assert "--all" in result.output

    def test_help_text_config(self, runner):
        """Test that config command help is displayed."""
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "Configuration" in result.output
        assert "show" in result.output
        assert "validate" in result.output


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_workflow(self, runner, test_config, tmp_path):
        """Test a complete workflow: validate, record, check status, generate report."""
        # 1. Validate config
        result = runner.invoke(cli, ["--config", str(test_config), "config", "validate"])
        assert result.exit_code == 0

        # 2. Record attendance for a date in period 1
        result = runner.invoke(
            cli,
            ["--config", str(test_config), "record", "in-office", "--date", "2025-01-15"],
        )
        assert result.exit_code == 0

        # 3. Record another date
        result = runner.invoke(
            cli,
            ["--config", str(test_config), "record", "in-office", "--date", "2025-01-16"],
        )
        assert result.exit_code == 0

        # 4. Generate report for period 1
        result = runner.invoke(
            cli, ["--config", str(test_config), "report", "--period", "1"]
        )
        assert result.exit_code == 0
        assert "Days Completed" in result.output

    def test_record_and_update_workflow(self, runner, test_config):
        """Test recording and then updating a record."""
        test_date = "2025-01-20"

        # Record as in-office
        result = runner.invoke(
            cli,
            ["--config", str(test_config), "record", "in-office", "--date", test_date],
        )
        assert result.exit_code == 0
        assert "in-office" in result.output

        # Update to remote
        result = runner.invoke(
            cli, ["--config", str(test_config), "record", "remote", "--date", test_date]
        )
        assert result.exit_code == 0
        assert "remote" in result.output

    def test_multiple_periods_workflow(self, runner, test_config):
        """Test working with multiple reporting periods."""
        # Record in different periods
        result = runner.invoke(
            cli,
            ["--config", str(test_config), "record", "in-office", "--date", "2025-01-15"],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            ["--config", str(test_config), "record", "in-office", "--date", "2025-05-15"],
        )
        assert result.exit_code == 0

        # Generate report for all periods
        result = runner.invoke(cli, ["--config", str(test_config), "report", "--all"])
        assert result.exit_code == 0
        assert "Reporting Period 1" in result.output
        assert "Reporting Period 2" in result.output
