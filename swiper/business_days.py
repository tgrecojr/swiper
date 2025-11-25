"""
Business day calculation utilities for the Swiper application.

This module provides the BusinessDayCalculator class for computing workdays,
identifying weekends, and handling exclusion days (holidays and company shutdowns).
"""

from datetime import date, timedelta


class BusinessDayCalculator:
    """
    Calculates business days excluding weekends and holidays.

    This class provides utilities for working with business days, including
    identifying weekends, checking exclusion days, counting workdays in a date range,
    and filtering exclusions within a period.

    Attributes:
        _exclusion_days: Set of dates that are excluded from workday calculations
                        (holidays, company shutdowns, etc.)
    """

    def __init__(self, exclusion_days: list[date]):
        """
        Initialize the BusinessDayCalculator with a list of exclusion days.

        Args:
            exclusion_days: List of dates to exclude from workday calculations
                          (e.g., holidays, company shutdowns)

        Implementation Notes:
            - Stores exclusion days as a set for O(1) lookup performance
            - Implements Requirement 4.2
        """
        self._exclusion_days = set(exclusion_days)

    def is_weekend(self, check_date: date) -> bool:
        """
        Check if a date falls on a weekend (Saturday or Sunday).

        Args:
            check_date: The date to check

        Returns:
            True if the date is Saturday (weekday 5) or Sunday (weekday 6),
            False otherwise

        Implementation Notes:
            - Uses Python's date.weekday() where Monday=0, Sunday=6
            - Implements Requirement 4.1

        Examples:
            >>> calc = BusinessDayCalculator([])
            >>> calc.is_weekend(date(2025, 8, 16))  # Saturday
            True
            >>> calc.is_weekend(date(2025, 8, 18))  # Monday
            False
        """
        return check_date.weekday() in [5, 6]  # Saturday=5, Sunday=6

    def is_exclusion_day(self, check_date: date) -> bool:
        """
        Check if a date is an exclusion day (holiday).

        Args:
            check_date: The date to check

        Returns:
            True if the date is in the exclusion days list, False otherwise

        Implementation Notes:
            - Uses set membership for O(1) performance
            - Implements Requirement 4.2

        Examples:
            >>> calc = BusinessDayCalculator([date(2025, 9, 1)])  # Labor Day
            >>> calc.is_exclusion_day(date(2025, 9, 1))
            True
            >>> calc.is_exclusion_day(date(2025, 9, 2))
            False
        """
        return check_date in self._exclusion_days

    def is_workday(self, check_date: date) -> bool:
        """
        Check if a date is a workday (weekday and not an exclusion day).

        A workday is defined as a date that is:
        1. NOT a weekend (Saturday or Sunday), AND
        2. NOT an exclusion day (holiday or company shutdown)

        Args:
            check_date: The date to check

        Returns:
            True if the date is a workday, False otherwise

        Implementation Notes:
            - Combines weekend and exclusion day checks
            - Implements Requirement 4.3

        Examples:
            >>> calc = BusinessDayCalculator([date(2025, 9, 1)])  # Labor Day Monday
            >>> calc.is_workday(date(2025, 8, 15))  # Friday
            True
            >>> calc.is_workday(date(2025, 8, 16))  # Saturday
            False
            >>> calc.is_workday(date(2025, 9, 1))  # Labor Day Monday
            False
        """
        return not self.is_weekend(check_date) and not self.is_exclusion_day(check_date)

    def count_workdays(self, start_date: date, end_date: date) -> int:
        """
        Count the total number of workdays in a date range (inclusive).

        Uses date arithmetic to efficiently calculate workdays by:
        1. Calculating total days in range
        2. Subtracting weekend days (calculated mathematically)
        3. Subtracting weekday exclusion days in range

        Args:
            start_date: First day of the range (inclusive)
            end_date: Last day of the range (inclusive)

        Returns:
            The count of workdays in the range

        Implementation Notes:
            - Uses date arithmetic instead of day-by-day iteration for efficiency
            - Calculates weekend days mathematically based on complete weeks + remaining days
            - Uses get_exclusions_in_range() for weekday exclusion count
            - Implements Requirements 4.4, 4.5, 4.6

        Examples:
            >>> calc = BusinessDayCalculator([date(2025, 9, 1)])  # Labor Day
            >>> # Aug 15 (Fri) to Aug 17 (Sun) = 1 workday (Friday only)
            >>> calc.count_workdays(date(2025, 8, 15), date(2025, 8, 17))
            1
            >>> # Aug 29 (Fri) to Sep 2 (Tue) = 2 workdays (Fri, Tue - excludes Labor Day Mon)
            >>> calc.count_workdays(date(2025, 8, 29), date(2025, 9, 2))
            2
        """
        # Calculate total days (inclusive)
        total_days = (end_date - start_date).days + 1

        # Count weekend days mathematically
        start_weekday = start_date.weekday()  # 0=Mon, 6=Sun
        complete_weeks = total_days // 7
        remaining_days = total_days % 7

        # Each complete week has 2 weekend days
        weekend_days = complete_weeks * 2

        # Check remaining days for weekends
        for i in range(remaining_days):
            if (start_weekday + i) % 7 in [5, 6]:  # Saturday=5, Sunday=6
                weekend_days += 1

        # Count weekday exclusions in range (get_exclusions_in_range already filters to weekdays)
        exclusion_count = len(self.get_exclusions_in_range(start_date, end_date))

        return total_days - weekend_days - exclusion_count

    def get_exclusions_in_range(self, start_date: date, end_date: date) -> list[date]:
        """
        Get exclusion days that fall within a date range.

        Filters the exclusion days to return only those that fall between
        the start_date and end_date (inclusive).

        Args:
            start_date: First day of the range (inclusive)
            end_date: Last day of the range (inclusive)

        Returns:
            Sorted list of exclusion days within the range

        Implementation Notes:
            - Only returns exclusion days that are weekdays (Mon-Fri)
            - This is important because only weekday exclusions reduce required days
            - Implements Requirement 4.7

        Examples:
            >>> holidays = [
            ...     date(2025, 9, 1),   # Labor Day (Mon)
            ...     date(2025, 11, 11), # Veterans Day (Tue)
            ...     date(2025, 12, 25)  # Christmas (Thu)
            ... ]
            >>> calc = BusinessDayCalculator(holidays)
            >>> # Get exclusions from Aug 15 to Nov 14
            >>> exclusions = calc.get_exclusions_in_range(
            ...     date(2025, 8, 15), date(2025, 11, 14)
            ... )
            >>> len(exclusions)
            2
            >>> # Should include Labor Day and Veterans Day, but not Christmas
        """
        exclusions_in_range = [
            exclusion_date
            for exclusion_date in self._exclusion_days
            if start_date <= exclusion_date <= end_date and not self.is_weekend(exclusion_date)
        ]
        return sorted(exclusions_in_range)
