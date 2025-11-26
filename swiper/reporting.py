"""
Reporting period calculations for the Swiper application.

This module provides the ReportingPeriodCalculator class for managing
reporting periods, calculating effective required days, and enriching
periods with exclusion day information.
"""

from datetime import date
from typing import Optional

from swiper.models import ReportingPeriod
from swiper.business_days import BusinessDayCalculator
from swiper.exceptions import ValidationError


class ReportingPeriodCalculator:
    """
    Manages reporting periods and calculates effective requirements.

    This class provides utilities for finding reporting periods by date,
    calculating effective required days after accounting for exclusions,
    and enriching period data with exclusion information.

    Attributes:
        _periods: List of reporting periods
        _business_day_calc: BusinessDayCalculator for exclusion calculations
    """

    def __init__(self, periods: list[ReportingPeriod], business_day_calc: BusinessDayCalculator):
        """
        Initialize the ReportingPeriodCalculator.

        Args:
            periods: List of ReportingPeriod instances
            business_day_calc: BusinessDayCalculator for exclusion day operations

        Implementation Notes:
            - Stores periods and business day calculator
            - Implements Requirement 3.1
        """
        self._periods = periods
        self._business_day_calc = business_day_calc

    def get_period_for_date(self, check_date: date) -> ReportingPeriod:
        """
        Find the reporting period that contains a specific date.

        Args:
            check_date: Date to find the period for

        Returns:
            ReportingPeriod that contains the date

        Raises:
            ValidationError: If no period contains the date

        Implementation Notes:
            - Iterates through periods to find match
            - Date must be within start_date and end_date (inclusive)
            - Implements Requirements 3.2, 3.3
        """
        for period in self._periods:
            if period.start_date <= check_date <= period.end_date:
                return period

        raise ValidationError(f"No reporting period defined for date {check_date}")

    def get_periods_for_date(self, check_date: date) -> list[ReportingPeriod]:
        """
        Find all reporting periods that contain a specific date.

        Since reporting periods can overlap, multiple periods may contain
        the same date. This method returns all matching periods.

        Args:
            check_date: Date to find the periods for

        Returns:
            List of ReportingPeriod instances that contain the date (may be empty)

        Implementation Notes:
            - Iterates through all periods to find matches
            - Date must be within start_date and end_date (inclusive)
            - Returns empty list if no periods contain the date
        """
        matching_periods = []
        for period in self._periods:
            if period.start_date <= check_date <= period.end_date:
                matching_periods.append(period)
        return matching_periods

    def get_current_period(self) -> ReportingPeriod:
        """
        Get the reporting period for today's date.

        Returns:
            ReportingPeriod that contains today's date

        Raises:
            ValidationError: If no period contains today's date

        Implementation Notes:
            - Calls get_period_for_date() with date.today()
            - Implements Requirement 3.4
        """
        return self.get_period_for_date(date.today())

    def get_current_periods(self) -> list[ReportingPeriod]:
        """
        Get all reporting periods for today's date.

        Since reporting periods can overlap, there may be multiple
        current periods active at the same time.

        Returns:
            List of ReportingPeriod instances that contain today's date (may be empty)

        Implementation Notes:
            - Calls get_periods_for_date() with date.today()
            - Returns list of all overlapping periods
        """
        return self.get_periods_for_date(date.today())

    def calculate_effective_required_days(self, period: ReportingPeriod) -> int:
        """
        Calculate effective required days for a period.

        Calculates the actual required in-office days after subtracting
        weekday exclusions (holidays that fall on weekdays).

        Args:
            period: ReportingPeriod to calculate for

        Returns:
            Effective required days (minimum 0)

        Implementation Notes:
            - Uses BusinessDayCalculator.get_exclusions_in_range()
            - Exclusions on weekends don't reduce requirements
            - Minimum effective required days is 0
            - Implements Requirements 5.1, 5.2, 5.3
        """
        # Get weekday exclusions in period range
        exclusions = self._business_day_calc.get_exclusions_in_range(
            period.start_date,
            period.end_date
        )

        # Calculate effective required days
        effective = period.baseline_required_days - len(exclusions)

        # Ensure minimum of 0
        return max(0, effective)

    def enrich_period_with_exclusions(self, period: ReportingPeriod) -> ReportingPeriod:
        """
        Enrich a reporting period with exclusion day information.

        Creates a new ReportingPeriod instance with populated exclusion_days
        and effective_required_days fields.

        Args:
            period: ReportingPeriod to enrich

        Returns:
            New ReportingPeriod instance with exclusion data populated

        Implementation Notes:
            - Gets exclusions using BusinessDayCalculator
            - Calculates effective required days
            - Returns new instance (doesn't modify input)
            - Implements Requirements 5.4, 5.5, 5.6
        """
        # Get weekday exclusions in period range
        exclusions = self._business_day_calc.get_exclusions_in_range(
            period.start_date,
            period.end_date
        )

        # Calculate effective required days
        effective_required = self.calculate_effective_required_days(period)

        # Create enriched period
        return ReportingPeriod(
            period_number=period.period_number,
            start_date=period.start_date,
            end_date=period.end_date,
            report_date=period.report_date,
            baseline_required_days=period.baseline_required_days,
            exclusion_days=exclusions,
            effective_required_days=effective_required
        )

    def get_period_by_number(self, period_number: int) -> Optional[ReportingPeriod]:
        """
        Get a reporting period by its period number.

        Args:
            period_number: Period number to find

        Returns:
            ReportingPeriod with matching period_number, or None if not found

        Implementation Notes:
            - Linear search through periods
            - Returns None if not found (not an error)
            - Implements Requirement 3.5
        """
        for period in self._periods:
            if period.period_number == period_number:
                return period
        return None

    def get_all_periods(self) -> list[ReportingPeriod]:
        """
        Get all configured reporting periods.

        Returns:
            List of all ReportingPeriod instances

        Implementation Notes:
            - Returns copy of periods list
            - Implements Requirement 3.5
        """
        return self._periods.copy()
