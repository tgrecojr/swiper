"""
Tests for the ConfigurationManager module.

This module tests all functionality related to configuration loading,
parsing, validation, and access for TOML and YAML configuration files.
"""

from datetime import date
from pathlib import Path
import pytest
from swiper.config import ConfigurationManager
from swiper.exceptions import ConfigurationError


class TestSuccessfulConfigLoading:
    """Test successful loading of valid configuration."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        settings = config_mgr.get_settings()

        assert settings is not None
        assert settings.policy.required_days_per_period == 20
        assert settings.data.reporting_periods_file == "tests/fixtures/valid_periods.toml"
        assert settings.data.exclusion_days_file == "tests/fixtures/valid_holidays.yaml"
        assert settings.data.attendance_data_dir == "tests/fixtures/data"

    def test_load_reporting_periods(self):
        """Test loading valid reporting periods."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        periods = config_mgr.get_reporting_periods()

        assert len(periods) == 2

        # Check first period
        assert periods[0].period_number == 1
        assert periods[0].start_date == date(2025, 8, 15)
        assert periods[0].end_date == date(2025, 11, 14)
        assert periods[0].report_date == date(2025, 11, 21)
        assert periods[0].baseline_required_days == 20

        # Check second period
        assert periods[1].period_number == 2
        assert periods[1].start_date == date(2025, 11, 15)
        assert periods[1].end_date == date(2026, 2, 13)
        assert periods[1].report_date == date(2026, 2, 20)

    def test_load_exclusion_days(self):
        """Test loading valid holiday calendar."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        exclusions = config_mgr.get_exclusion_days()

        assert len(exclusions) == 5
        assert date(2025, 9, 1) in exclusions  # Labor Day
        assert date(2025, 11, 11) in exclusions  # Veterans Day
        assert date(2025, 11, 27) in exclusions  # Thanksgiving
        assert date(2025, 12, 25) in exclusions  # Christmas
        assert date(2026, 1, 1) in exclusions  # New Year's Day

    def test_validate_all_success(self):
        """Test that validate_all returns True for valid configuration."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        assert config_mgr.validate_all() is True


class TestMissingConfigFile:
    """Test error handling for missing configuration files."""

    def test_missing_main_config(self):
        """Test error when main config file doesn't exist."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/nonexistent.toml"))

        assert "Configuration file not found" in str(exc_info.value)

    def test_missing_periods_file(self):
        """Test error when periods file doesn't exist."""
        # Create a temporary config that references a non-existent periods file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""[policy]
required_days_per_period = 20

[data]
reporting_periods_file = "tests/fixtures/missing_periods.toml"
exclusion_days_file = "tests/fixtures/valid_holidays.yaml"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "Reporting periods file not found" in str(exc_info.value)
        finally:
            os.unlink(temp_config)

    def test_missing_exclusions_file(self):
        """Test error when exclusion days file doesn't exist."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""[policy]
required_days_per_period = 20

[data]
reporting_periods_file = "tests/fixtures/valid_periods.toml"
exclusion_days_file = "tests/fixtures/missing_holidays.yaml"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "Exclusion days file not found" in str(exc_info.value)
        finally:
            os.unlink(temp_config)


class TestInvalidTomlSyntax:
    """Test error handling for invalid TOML syntax."""

    def test_invalid_toml_syntax(self):
        """Test error when TOML file has syntax errors."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/invalid_toml.toml"))

        assert "Invalid TOML syntax" in str(exc_info.value)


class TestMissingRequiredFields:
    """Test validation of required configuration fields."""

    def test_missing_data_section(self):
        """Test error when required data section is missing."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/missing_fields.toml"))

        assert "Configuration validation failed" in str(exc_info.value)
        assert "data" in str(exc_info.value).lower()


class TestInvalidPolicyValues:
    """Test validation of policy values."""

    def test_negative_required_days(self):
        """Test error when required_days_per_period is negative."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/invalid_policy.toml"))

        assert "Configuration validation failed" in str(exc_info.value)
        assert "greater than 0" in str(exc_info.value)

    def test_zero_required_days(self):
        """Test error when required_days_per_period is zero."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""[policy]
required_days_per_period = 0

[data]
reporting_periods_file = "tests/fixtures/valid_periods.toml"
exclusion_days_file = "tests/fixtures/valid_holidays.yaml"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "greater than 0" in str(exc_info.value)
        finally:
            os.unlink(temp_config)


class TestInvalidReportingPeriods:
    """Test validation of reporting period definitions."""

    def test_end_date_before_start_date(self):
        """Test error when end_date is before start_date."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/config_with_invalid_periods.toml"))

        assert "Invalid reporting period definition" in str(exc_info.value)
        assert "end_date must be after" in str(exc_info.value)

    def test_negative_period_number(self):
        """Test error when period_number is negative or zero."""
        import tempfile
        import os

        # Create temporary invalid periods file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""[[periods]]
period_number = 0
start_date = 2025-08-15
end_date = 2025-11-14
report_date = 2025-11-21
""")
            temp_periods = f.name

        # Create temporary config referencing it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(f"""[policy]
required_days_per_period = 20

[data]
reporting_periods_file = "{temp_periods}"
exclusion_days_file = "tests/fixtures/valid_holidays.yaml"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "Invalid reporting period definition" in str(exc_info.value)
            assert "greater than 0" in str(exc_info.value)
        finally:
            os.unlink(temp_periods)
            os.unlink(temp_config)

    def test_missing_periods_array(self):
        """Test error when periods TOML doesn't contain periods array."""
        import tempfile
        import os

        # Create temporary periods file without periods array
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""# No periods array
[other_section]
value = 1
""")
            temp_periods = f.name

        # Create temporary config referencing it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(f"""[policy]
required_days_per_period = 20

[data]
reporting_periods_file = "{temp_periods}"
exclusion_days_file = "tests/fixtures/valid_holidays.yaml"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "must contain a 'periods' array" in str(exc_info.value)
        finally:
            os.unlink(temp_periods)
            os.unlink(temp_config)


class TestInvalidYaml:
    """Test error handling for invalid YAML syntax."""

    def test_invalid_yaml_syntax(self):
        """Test error when YAML file has syntax errors."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigurationManager(Path("tests/fixtures/config_with_invalid_yaml.toml"))

        assert "Invalid YAML syntax" in str(exc_info.value)

    def test_missing_holidays_list(self):
        """Test error when YAML doesn't contain holidays list."""
        import tempfile
        import os

        # Create temporary YAML file without holidays list
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("# No holidays list\nother_field: value\n")
            temp_yaml = f.name

        # Create temporary config referencing it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(f"""[policy]
required_days_per_period = 20

[data]
reporting_periods_file = "tests/fixtures/valid_periods.toml"
exclusion_days_file = "{temp_yaml}"
attendance_data_dir = "tests/fixtures/data"
""")
            temp_config = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager(Path(temp_config))

            assert "must contain a 'holidays' list" in str(exc_info.value)
        finally:
            os.unlink(temp_yaml)
            os.unlink(temp_config)


class TestAccessMethods:
    """Test configuration accessor methods."""

    def test_get_settings_returns_copy(self):
        """Test that get_settings returns the configuration settings."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        settings1 = config_mgr.get_settings()
        settings2 = config_mgr.get_settings()

        # Should return the same settings
        assert settings1.policy.required_days_per_period == settings2.policy.required_days_per_period

    def test_get_reporting_periods_returns_copy(self):
        """Test that get_reporting_periods returns a copy of the periods list."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        periods1 = config_mgr.get_reporting_periods()
        periods2 = config_mgr.get_reporting_periods()

        # Should return copies (different list objects)
        assert periods1 is not periods2
        # But with same content
        assert len(periods1) == len(periods2)
        assert periods1[0].period_number == periods2[0].period_number

    def test_get_exclusion_days_returns_copy(self):
        """Test that get_exclusion_days returns a copy of the exclusion list."""
        config_mgr = ConfigurationManager(Path("tests/fixtures/valid_config.toml"))
        exclusions1 = config_mgr.get_exclusion_days()
        exclusions2 = config_mgr.get_exclusion_days()

        # Should return copies (different list objects)
        assert exclusions1 is not exclusions2
        # But with same content
        assert len(exclusions1) == len(exclusions2)
        assert exclusions1[0] == exclusions2[0]
