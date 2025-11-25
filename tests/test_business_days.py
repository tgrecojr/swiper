"""
Tests for the BusinessDayCalculator module.

This module tests all functionality related to business day calculations,
including weekend detection, exclusion day handling, and workday counting.
"""

from datetime import date
import pytest
from swiper.business_days import BusinessDayCalculator


class TestIsWeekend:
    """Test the is_weekend() method."""

    def test_saturday_is_weekend(self):
        """Test that Saturday is correctly identified as a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 16)) is True  # Saturday

    def test_sunday_is_weekend(self):
        """Test that Sunday is correctly identified as a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 17)) is True  # Sunday

    def test_monday_is_not_weekend(self):
        """Test that Monday is not a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 18)) is False  # Monday

    def test_tuesday_is_not_weekend(self):
        """Test that Tuesday is not a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 19)) is False  # Tuesday

    def test_wednesday_is_not_weekend(self):
        """Test that Wednesday is not a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 20)) is False  # Wednesday

    def test_thursday_is_not_weekend(self):
        """Test that Thursday is not a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 21)) is False  # Thursday

    def test_friday_is_not_weekend(self):
        """Test that Friday is not a weekend."""
        calc = BusinessDayCalculator([])
        assert calc.is_weekend(date(2025, 8, 15)) is False  # Friday


class TestIsExclusionDay:
    """Test the is_exclusion_day() method."""

    def test_holiday_is_exclusion_day(self):
        """Test that a configured holiday is identified as an exclusion day."""
        labor_day = date(2025, 9, 1)
        calc = BusinessDayCalculator([labor_day])
        assert calc.is_exclusion_day(labor_day) is True

    def test_non_holiday_is_not_exclusion_day(self):
        """Test that a regular day is not an exclusion day."""
        labor_day = date(2025, 9, 1)
        calc = BusinessDayCalculator([labor_day])
        assert calc.is_exclusion_day(date(2025, 9, 2)) is False

    def test_multiple_holidays(self):
        """Test checking multiple exclusion days."""
        labor_day = date(2025, 9, 1)
        veterans_day = date(2025, 11, 11)
        calc = BusinessDayCalculator([labor_day, veterans_day])

        assert calc.is_exclusion_day(labor_day) is True
        assert calc.is_exclusion_day(veterans_day) is True
        assert calc.is_exclusion_day(date(2025, 10, 1)) is False

    def test_empty_exclusion_list(self):
        """Test that with no exclusions, all days are non-exclusion days."""
        calc = BusinessDayCalculator([])
        assert calc.is_exclusion_day(date(2025, 9, 1)) is False


class TestIsWorkday:
    """Test the is_workday() method combining weekend and exclusion checks."""

    def test_regular_weekday_is_workday(self):
        """Test that a regular weekday (not a holiday) is a workday."""
        calc = BusinessDayCalculator([])
        assert calc.is_workday(date(2025, 8, 15)) is True  # Friday

    def test_saturday_is_not_workday(self):
        """Test that Saturday is not a workday."""
        calc = BusinessDayCalculator([])
        assert calc.is_workday(date(2025, 8, 16)) is False  # Saturday

    def test_sunday_is_not_workday(self):
        """Test that Sunday is not a workday."""
        calc = BusinessDayCalculator([])
        assert calc.is_workday(date(2025, 8, 17)) is False  # Sunday

    def test_holiday_weekday_is_not_workday(self):
        """Test that a holiday on a weekday is not a workday."""
        labor_day = date(2025, 9, 1)  # Monday
        calc = BusinessDayCalculator([labor_day])
        assert calc.is_workday(labor_day) is False

    def test_weekday_after_holiday_is_workday(self):
        """Test that the day after a holiday is a workday."""
        labor_day = date(2025, 9, 1)  # Monday
        calc = BusinessDayCalculator([labor_day])
        assert calc.is_workday(date(2025, 9, 2)) is True  # Tuesday

    def test_holiday_on_weekend_does_not_affect_workdays(self):
        """Test that a holiday falling on a weekend doesn't impact other days."""
        # Christmas 2025 is on Thursday, but let's pretend it's on Saturday
        christmas_saturday = date(2025, 12, 27)  # Saturday
        calc = BusinessDayCalculator([christmas_saturday])
        # Friday before is still a workday
        assert calc.is_workday(date(2025, 12, 26)) is True  # Friday
        # Saturday is not a workday (already weekend)
        assert calc.is_workday(christmas_saturday) is False


class TestCountWorkdays:
    """Test the count_workdays() method with various scenarios."""

    def test_single_weekday_no_holidays(self):
        """Test counting a single workday with no holidays."""
        calc = BusinessDayCalculator([])
        # Friday to Friday = 1 day
        count = calc.count_workdays(date(2025, 8, 15), date(2025, 8, 15))
        assert count == 1

    def test_full_week_no_holidays(self):
        """Test counting a full week (Mon-Sun) with no holidays."""
        calc = BusinessDayCalculator([])
        # Monday Aug 18 to Sunday Aug 24 = 5 workdays
        count = calc.count_workdays(date(2025, 8, 18), date(2025, 8, 24))
        assert count == 5

    def test_weekend_only(self):
        """Test counting a weekend yields zero workdays."""
        calc = BusinessDayCalculator([])
        # Saturday to Sunday = 0 workdays
        count = calc.count_workdays(date(2025, 8, 16), date(2025, 8, 17))
        assert count == 0

    def test_workdays_with_holiday(self):
        """Test counting workdays excluding a holiday."""
        labor_day = date(2025, 9, 1)  # Monday
        calc = BusinessDayCalculator([labor_day])
        # Fri Aug 29 to Tue Sep 2 = 2 workdays (Fri, Tue - excluding Labor Day Mon and weekend)
        count = calc.count_workdays(date(2025, 8, 29), date(2025, 9, 2))
        assert count == 2

    def test_workdays_with_multiple_holidays(self):
        """Test counting workdays with multiple holidays in range."""
        thanksgiving = date(2025, 11, 27)  # Thursday
        black_friday = date(2025, 11, 28)  # Friday
        calc = BusinessDayCalculator([thanksgiving, black_friday])
        # Mon Nov 24 to Fri Nov 28 = 3 workdays (Mon, Tue, Wed only)
        count = calc.count_workdays(date(2025, 11, 24), date(2025, 11, 28))
        assert count == 3

    def test_entire_month_with_holidays(self):
        """Test counting workdays for a full month with holidays."""
        # September 2025: Labor Day on Sept 1 (Mon)
        # 30 days total, with 4 full weekends (8 days) + 1 holiday = 21 workdays
        labor_day = date(2025, 9, 1)
        calc = BusinessDayCalculator([labor_day])
        count = calc.count_workdays(date(2025, 9, 1), date(2025, 9, 30))
        assert count == 21  # 30 - 8 weekend days - 1 holiday

    def test_reporting_period_example(self):
        """Test a realistic 13-week reporting period scenario."""
        # Period 1: Aug 15, 2025 to Nov 14, 2025 (92 days)
        # Holidays: Labor Day (Sep 1), Veterans Day (Nov 11)
        holidays = [
            date(2025, 9, 1),   # Labor Day (Monday)
            date(2025, 11, 11)  # Veterans Day (Tuesday)
        ]
        calc = BusinessDayCalculator(holidays)
        count = calc.count_workdays(date(2025, 8, 15), date(2025, 11, 14))
        # 92 days total (Aug 15-31: 17, Sep: 30, Oct: 31, Nov 1-14: 14)
        # 26 weekend days
        # 2 holidays (weekdays)
        # Expected: 92 - 26 - 2 = 64 workdays
        assert count == 64


class TestGetExclusionsInRange:
    """Test the get_exclusions_in_range() method."""

    def test_holidays_inside_range(self):
        """Test that holidays within the range are returned."""
        labor_day = date(2025, 9, 1)
        veterans_day = date(2025, 11, 11)
        calc = BusinessDayCalculator([labor_day, veterans_day])

        exclusions = calc.get_exclusions_in_range(
            date(2025, 8, 15),  # Aug 15
            date(2025, 11, 14)  # Nov 14
        )

        assert len(exclusions) == 2
        assert labor_day in exclusions
        assert veterans_day in exclusions

    def test_holidays_outside_range(self):
        """Test that holidays outside the range are not returned."""
        labor_day = date(2025, 9, 1)
        christmas = date(2025, 12, 25)
        calc = BusinessDayCalculator([labor_day, christmas])

        exclusions = calc.get_exclusions_in_range(
            date(2025, 8, 15),  # Aug 15
            date(2025, 11, 14)  # Nov 14
        )

        assert len(exclusions) == 1
        assert labor_day in exclusions
        assert christmas not in exclusions

    def test_no_holidays_in_range(self):
        """Test that an empty list is returned when no holidays in range."""
        christmas = date(2025, 12, 25)
        new_years = date(2026, 1, 1)
        calc = BusinessDayCalculator([christmas, new_years])

        exclusions = calc.get_exclusions_in_range(
            date(2025, 8, 15),
            date(2025, 11, 14)
        )

        assert len(exclusions) == 0

    def test_exclusions_on_weekends_not_included(self):
        """Test that exclusion days falling on weekends are not returned."""
        # If a holiday falls on a weekend, it shouldn't reduce required days
        saturday_holiday = date(2025, 8, 16)  # Saturday
        sunday_holiday = date(2025, 8, 17)  # Sunday
        monday_holiday = date(2025, 8, 18)  # Monday
        calc = BusinessDayCalculator([saturday_holiday, sunday_holiday, monday_holiday])

        exclusions = calc.get_exclusions_in_range(
            date(2025, 8, 15),
            date(2025, 8, 20)
        )

        # Only Monday holiday should be included
        assert len(exclusions) == 1
        assert monday_holiday in exclusions
        assert saturday_holiday not in exclusions
        assert sunday_holiday not in exclusions

    def test_exclusions_returned_sorted(self):
        """Test that exclusions are returned in sorted order."""
        holidays = [
            date(2025, 11, 11),  # Veterans Day
            date(2025, 9, 1),    # Labor Day
            date(2025, 10, 13)   # Indigenous Peoples' Day
        ]
        calc = BusinessDayCalculator(holidays)

        exclusions = calc.get_exclusions_in_range(
            date(2025, 8, 15),
            date(2025, 11, 14)
        )

        assert exclusions == [
            date(2025, 9, 1),
            date(2025, 10, 13),
            date(2025, 11, 11)
        ]

    def test_boundary_dates_included(self):
        """Test that holidays on the boundary dates are included."""
        start_holiday = date(2025, 8, 15)  # Friday
        end_holiday = date(2025, 11, 14)   # Friday
        calc = BusinessDayCalculator([start_holiday, end_holiday])

        exclusions = calc.get_exclusions_in_range(start_holiday, end_holiday)

        assert len(exclusions) == 2
        assert start_holiday in exclusions
        assert end_holiday in exclusions
