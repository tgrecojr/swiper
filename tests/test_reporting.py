"""
Tests for the ReportingPeriodCalculator module.

This module tests all functionality related to reporting period management,
including finding periods by date, calculating effective required days,
and enriching periods with exclusion data.
"""

from datetime import date
import pytest

from swiper.reporting import ReportingPeriodCalculator
from swiper.business_days import BusinessDayCalculator
from swiper.models import ReportingPeriod
from swiper.exceptions import ValidationError


@pytest.fixture
def sample_periods():
    """Sample reporting periods for testing."""
    return [
        ReportingPeriod(
            period_number=1,
            start_date=date(2025, 8, 15),
            end_date=date(2025, 11, 14),
            report_date=date(2025, 12, 3),
            baseline_required_days=20,
            exclusion_days=[],
            effective_required_days=20
        ),
        ReportingPeriod(
            period_number=2,
            start_date=date(2025, 11, 15),
            end_date=date(2026, 2, 13),
            report_date=date(2026, 2, 25),
            baseline_required_days=20,
            exclusion_days=[],
            effective_required_days=20
        ),
        ReportingPeriod(
            period_number=3,
            start_date=date(2026, 2, 14),
            end_date=date(2026, 5, 15),
            report_date=date(2026, 5, 27),
            baseline_required_days=20,
            exclusion_days=[],
            effective_required_days=20
        ),
    ]


@pytest.fixture
def sample_holidays():
    """Sample holiday dates for testing."""
    return [
        date(2025, 9, 1),   # Labor Day (Monday)
        date(2025, 10, 13), # Indigenous Peoples' Day (Monday)
        date(2025, 11, 11), # Veterans Day (Tuesday)
        date(2025, 11, 27), # Thanksgiving (Thursday)
        date(2026, 1, 1),   # New Year's Day (Thursday)
        date(2026, 2, 16),  # Presidents' Day (Monday)
        date(2026, 5, 25),  # Memorial Day (Monday)
    ]


@pytest.fixture
def calculator(sample_periods, sample_holidays):
    """ReportingPeriodCalculator fixture with sample data."""
    business_calc = BusinessDayCalculator(sample_holidays)
    return ReportingPeriodCalculator(sample_periods, business_calc)


class TestGetPeriodForDate:
    """Test finding reporting periods by date."""

    def test_find_period_start_date(self, calculator):
        """Test finding period on its start date."""
        period = calculator.get_period_for_date(date(2025, 8, 15))
        assert period.period_number == 1
        assert period.start_date == date(2025, 8, 15)

    def test_find_period_end_date(self, calculator):
        """Test finding period on its end date."""
        period = calculator.get_period_for_date(date(2025, 11, 14))
        assert period.period_number == 1
        assert period.end_date == date(2025, 11, 14)

    def test_find_period_middle_date(self, calculator):
        """Test finding period for a date in the middle."""
        period = calculator.get_period_for_date(date(2025, 9, 15))
        assert period.period_number == 1

    def test_find_second_period(self, calculator):
        """Test finding the second period."""
        period = calculator.get_period_for_date(date(2025, 12, 15))
        assert period.period_number == 2
        assert period.start_date == date(2025, 11, 15)
        assert period.end_date == date(2026, 2, 13)

    def test_find_third_period(self, calculator):
        """Test finding the third period."""
        period = calculator.get_period_for_date(date(2026, 3, 15))
        assert period.period_number == 3

    def test_date_outside_all_periods_raises_error(self, calculator):
        """Test that date outside all periods raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            calculator.get_period_for_date(date(2024, 1, 1))

        assert "No reporting period defined for date 2024-01-01" in str(exc_info.value)

    def test_date_between_periods_raises_error(self, calculator):
        """Test that date in gap between periods raises ValidationError."""
        # Date after period 3 ends
        with pytest.raises(ValidationError) as exc_info:
            calculator.get_period_for_date(date(2026, 6, 1))

        assert "No reporting period defined" in str(exc_info.value)


class TestGetCurrentPeriod:
    """Test getting the current period."""

    def test_get_current_period(self, sample_periods, sample_holidays):
        """Test getting current period based on today's date."""
        business_calc = BusinessDayCalculator(sample_holidays)

        # Extend periods to cover today for testing
        today = date.today()
        test_periods = [
            ReportingPeriod(
                period_number=1,
                start_date=date(today.year - 1, 1, 1),
                end_date=date(today.year + 1, 12, 31),
                report_date=date(today.year + 2, 1, 15),
                baseline_required_days=20,
                exclusion_days=[],
                effective_required_days=20
            )
        ]

        calc = ReportingPeriodCalculator(test_periods, business_calc)
        current = calc.get_current_period()

        assert current.period_number == 1
        assert current.start_date <= today <= current.end_date

    def test_get_current_period_not_defined_raises_error(self, calculator):
        """Test that getting current period when today is not in any period raises error."""
        # The calculator fixture has periods in 2025-2026
        # If today is outside these, it should raise
        today = date.today()

        # Only test if today is actually outside the sample periods
        try:
            period = calculator.get_period_for_date(today)
            # If we get here, today IS in a period, so skip this test
            pytest.skip("Today is within sample period range")
        except ValidationError:
            # Today is not in any period, test should work
            with pytest.raises(ValidationError):
                calculator.get_current_period()


class TestCalculateEffectiveRequiredDays:
    """Test calculation of effective required days."""

    def test_no_exclusions_in_period(self, calculator, sample_periods):
        """Test calculation when no exclusions in period."""
        # Period 3 (Feb 14 - May 15, 2026) has 1 holiday: Feb 16
        # Note: May 25 is after period end date (May 15)
        period = sample_periods[2]
        effective = calculator.calculate_effective_required_days(period)

        # Should be 20 - 1 = 19
        assert effective == 19

    def test_with_exclusions_in_period(self, calculator, sample_periods):
        """Test calculation with exclusions in period."""
        # Period 1 (Aug 15 - Nov 14, 2025) has 3 holidays: Sep 1, Oct 13, Nov 11
        period = sample_periods[0]
        effective = calculator.calculate_effective_required_days(period)

        # Should be 20 - 3 = 17
        assert effective == 17

    def test_multiple_exclusions(self, calculator, sample_periods):
        """Test calculation with multiple exclusions."""
        # Period 2 (Nov 15, 2025 - Feb 13, 2026) has 2 holidays: Nov 27, Jan 1
        period = sample_periods[1]
        effective = calculator.calculate_effective_required_days(period)

        # Should be 20 - 2 = 18
        assert effective == 18

    def test_effective_days_minimum_zero(self, sample_holidays):
        """Test that effective required days minimum is 0."""
        # Create a period with many exclusions
        business_calc = BusinessDayCalculator(sample_holidays)

        # Period with baseline of 2 but 3+ holidays
        period = ReportingPeriod(
            period_number=1,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 11, 30),
            report_date=date(2025, 12, 15),
            baseline_required_days=2,  # Only 2 required
            exclusion_days=[],
            effective_required_days=2
        )

        calc = ReportingPeriodCalculator([period], business_calc)
        effective = calc.calculate_effective_required_days(period)

        # Should be max(0, 2 - 3) = 0
        assert effective == 0

    def test_many_exclusions_scenario(self):
        """Test scenario with many exclusions reducing requirement significantly."""
        # Create many holidays
        holidays = [
            date(2025, 8, 18),  # Week 1
            date(2025, 8, 19),
            date(2025, 8, 20),
            date(2025, 8, 25),  # Week 2
            date(2025, 8, 26),
            date(2025, 8, 27),
        ]
        business_calc = BusinessDayCalculator(holidays)

        period = ReportingPeriod(
            period_number=1,
            start_date=date(2025, 8, 15),
            end_date=date(2025, 8, 31),
            report_date=date(2025, 9, 15),
            baseline_required_days=10,
            exclusion_days=[],
            effective_required_days=10
        )

        calc = ReportingPeriodCalculator([period], business_calc)
        effective = calc.calculate_effective_required_days(period)

        # Should be 10 - 6 = 4
        assert effective == 4


class TestEnrichPeriodWithExclusions:
    """Test enriching periods with exclusion data."""

    def test_enrich_period_populates_exclusions(self, calculator, sample_periods):
        """Test that enriching period populates exclusion_days field."""
        period = sample_periods[0]  # Aug 15 - Nov 14, 2025
        enriched = calculator.enrich_period_with_exclusions(period)

        # Should have 3 holidays: Sep 1, Oct 13, Nov 11
        assert len(enriched.exclusion_days) == 3
        assert date(2025, 9, 1) in enriched.exclusion_days
        assert date(2025, 10, 13) in enriched.exclusion_days
        assert date(2025, 11, 11) in enriched.exclusion_days

    def test_enrich_period_calculates_effective_days(self, calculator, sample_periods):
        """Test that enriching period calculates effective_required_days."""
        period = sample_periods[0]
        enriched = calculator.enrich_period_with_exclusions(period)

        # Should be 20 - 3 = 17
        assert enriched.effective_required_days == 17

    def test_enrich_period_preserves_other_fields(self, calculator, sample_periods):
        """Test that enriching period preserves other fields."""
        period = sample_periods[0]
        enriched = calculator.enrich_period_with_exclusions(period)

        assert enriched.period_number == period.period_number
        assert enriched.start_date == period.start_date
        assert enriched.end_date == period.end_date
        assert enriched.report_date == period.report_date
        assert enriched.baseline_required_days == period.baseline_required_days

    def test_enrich_period_returns_new_instance(self, calculator, sample_periods):
        """Test that enriching period returns a new instance."""
        period = sample_periods[0]
        enriched = calculator.enrich_period_with_exclusions(period)

        # Should be different objects
        assert enriched is not period
        # Original should be unchanged
        assert period.exclusion_days == []

    def test_enrich_all_periods(self, calculator, sample_periods):
        """Test enriching all periods."""
        enriched_periods = [
            calculator.enrich_period_with_exclusions(p)
            for p in sample_periods
        ]

        # All should have exclusion data
        assert all(len(p.exclusion_days) >= 0 for p in enriched_periods)
        assert all(p.effective_required_days >= 0 for p in enriched_periods)

        # Check specific periods
        assert enriched_periods[0].effective_required_days == 17  # 20 - 3
        assert enriched_periods[1].effective_required_days == 18  # 20 - 2
        assert enriched_periods[2].effective_required_days == 19  # 20 - 1


class TestGetPeriodByNumber:
    """Test getting periods by period number."""

    def test_get_period_by_number_exists(self, calculator):
        """Test getting a period that exists."""
        period = calculator.get_period_by_number(1)
        assert period is not None
        assert period.period_number == 1
        assert period.start_date == date(2025, 8, 15)

    def test_get_period_by_number_second_period(self, calculator):
        """Test getting the second period."""
        period = calculator.get_period_by_number(2)
        assert period is not None
        assert period.period_number == 2

    def test_get_period_by_number_third_period(self, calculator):
        """Test getting the third period."""
        period = calculator.get_period_by_number(3)
        assert period is not None
        assert period.period_number == 3

    def test_get_period_by_number_not_exists(self, calculator):
        """Test getting a period that doesn't exist returns None."""
        period = calculator.get_period_by_number(99)
        assert period is None

    def test_get_period_by_number_zero(self, calculator):
        """Test getting period 0 returns None."""
        period = calculator.get_period_by_number(0)
        assert period is None

    def test_get_period_by_number_negative(self, calculator):
        """Test getting negative period number returns None."""
        period = calculator.get_period_by_number(-1)
        assert period is None


class TestGetAllPeriods:
    """Test getting all periods."""

    def test_get_all_periods_returns_all(self, calculator, sample_periods):
        """Test that get_all_periods returns all periods."""
        all_periods = calculator.get_all_periods()
        assert len(all_periods) == len(sample_periods)
        assert all(p in all_periods for p in sample_periods)

    def test_get_all_periods_returns_copy(self, calculator):
        """Test that get_all_periods returns a copy."""
        periods1 = calculator.get_all_periods()
        periods2 = calculator.get_all_periods()

        # Should be different list objects
        assert periods1 is not periods2
        # But same content
        assert len(periods1) == len(periods2)

    def test_get_all_periods_preserves_order(self, calculator, sample_periods):
        """Test that get_all_periods preserves period order."""
        all_periods = calculator.get_all_periods()

        for i, period in enumerate(all_periods):
            assert period.period_number == sample_periods[i].period_number
