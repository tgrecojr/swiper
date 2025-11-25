"""
Compliance checking for the Swiper application.

This module provides the ComplianceChecker class for determining whether
attendance requirements are being met, calculating risk levels, and
providing predictive compliance analysis.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from swiper.models import ReportingPeriod
from swiper.reporting import ReportingPeriodCalculator
from swiper.business_days import BusinessDayCalculator
from swiper.storage import AttendanceStore


# Type alias for risk levels
RiskLevel = Literal["impossible", "critical", "at-risk", "possible", "achieved"]


@dataclass
class ComplianceStatus:
    """
    Represents the compliance status for a reporting period.

    Attributes:
        period: The reporting period being checked
        as_of_date: The date as of which compliance is calculated
        in_office_days: Number of in-office days recorded so far
        effective_required_days: Required days after accounting for exclusions
        remaining_required_days: Number of additional in-office days needed
        remaining_workdays: Number of workdays remaining in the period
        risk_level: Compliance risk assessment
        is_compliant: Whether requirement is currently met
        is_achievable: Whether requirement can still be met
    """
    period: ReportingPeriod
    as_of_date: date
    in_office_days: int
    effective_required_days: int
    remaining_required_days: int
    remaining_workdays: int
    risk_level: RiskLevel
    is_compliant: bool
    is_achievable: bool


class ComplianceChecker:
    """
    Checks compliance with in-office attendance requirements.

    This class provides utilities for calculating compliance status,
    determining risk levels, and performing predictive analysis for
    reporting periods.

    Attributes:
        _period_calc: ReportingPeriodCalculator for period operations
        _business_day_calc: BusinessDayCalculator for workday calculations
        _store: AttendanceStore for loading attendance records
    """

    def __init__(
        self,
        period_calc: ReportingPeriodCalculator,
        business_day_calc: BusinessDayCalculator,
        store: AttendanceStore
    ):
        """
        Initialize the ComplianceChecker.

        Args:
            period_calc: ReportingPeriodCalculator instance
            business_day_calc: BusinessDayCalculator instance
            store: AttendanceStore instance

        Implementation Notes:
            - Stores dependencies for compliance calculations
            - Implements Requirement 4.1
        """
        self._period_calc = period_calc
        self._business_day_calc = business_day_calc
        self._store = store

    def calculate_compliance_status(
        self,
        period: ReportingPeriod,
        as_of_date: date | None = None
    ) -> ComplianceStatus:
        """
        Calculate comprehensive compliance status for a reporting period.

        Args:
            period: ReportingPeriod to check compliance for
            as_of_date: Date to calculate compliance as of (defaults to today)

        Returns:
            ComplianceStatus with all compliance metrics

        Implementation Notes:
            - Uses today's date if as_of_date not provided
            - Loads attendance records from storage
            - Counts in-office days in the period up to as_of_date
            - Calculates effective required days using period calculator
            - Determines remaining required days and workdays
            - Calculates risk level
            - Implements Requirements 4.2, 4.3, 4.4
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Get effective required days for this period
        effective_required = self._period_calc.calculate_effective_required_days(period)

        # Load attendance records for the period up to as_of_date
        end_for_calculation = min(as_of_date, period.end_date)
        records = self._store.load_records(period.start_date, end_for_calculation)

        # Count in-office days
        in_office_days = sum(1 for r in records if r.status == "in-office")

        # Calculate remaining required days
        remaining_required = max(0, effective_required - in_office_days)

        # Calculate remaining workdays from as_of_date to end of period
        if as_of_date >= period.end_date:
            remaining_workdays = 0
        else:
            # Start counting from the day after as_of_date
            from datetime import timedelta
            count_start = as_of_date + timedelta(days=1)
            remaining_workdays = self._business_day_calc.count_workdays(
                count_start,
                period.end_date
            )

        # Determine compliance status
        is_compliant = in_office_days >= effective_required
        is_achievable = remaining_required <= remaining_workdays

        # Calculate risk level
        risk_level = self._calculate_risk_level(
            remaining_required,
            remaining_workdays,
            is_compliant
        )

        return ComplianceStatus(
            period=period,
            as_of_date=as_of_date,
            in_office_days=in_office_days,
            effective_required_days=effective_required,
            remaining_required_days=remaining_required,
            remaining_workdays=remaining_workdays,
            risk_level=risk_level,
            is_compliant=is_compliant,
            is_achievable=is_achievable
        )

    def _calculate_risk_level(
        self,
        remaining_required: int,
        remaining_workdays: int,
        is_compliant: bool
    ) -> RiskLevel:
        """
        Calculate the risk level for compliance.

        Args:
            remaining_required: Number of in-office days still needed
            remaining_workdays: Number of workdays remaining
            is_compliant: Whether requirement is currently met

        Returns:
            Risk level classification

        Implementation Notes:
            - "achieved": Requirement already met (remaining_required = 0)
            - "impossible": Cannot meet requirement even with all remaining workdays
            - "critical": Can meet requirement but requires all remaining workdays
            - "at-risk": Can meet requirement but with less than 5 days buffer
            - "possible": Can meet requirement with 5+ days buffer
            - Implements Requirement 7.1, 7.2, 7.3, 7.4, 7.5
        """
        # Already met requirement
        if is_compliant:
            return "achieved"

        # Cannot meet requirement
        if remaining_required > remaining_workdays:
            return "impossible"

        # Calculate buffer days (how many extra workdays beyond what's required)
        buffer_days = remaining_workdays - remaining_required

        # Need all remaining workdays
        if buffer_days == 0:
            return "critical"

        # Can meet but with less than 5 days buffer
        if buffer_days < 5:
            return "at-risk"

        # Can meet with comfortable buffer
        return "possible"

    def get_remaining_required_days(
        self,
        period: ReportingPeriod,
        as_of_date: date | None = None
    ) -> int:
        """
        Get the number of in-office days still required for compliance.

        Args:
            period: ReportingPeriod to check
            as_of_date: Date to calculate as of (defaults to today)

        Returns:
            Number of additional in-office days needed (minimum 0)

        Implementation Notes:
            - Convenience method for getting just remaining required days
            - Implements Requirement 4.5
        """
        status = self.calculate_compliance_status(period, as_of_date)
        return status.remaining_required_days

    def is_achievable(
        self,
        period: ReportingPeriod,
        as_of_date: date | None = None
    ) -> bool:
        """
        Check if the attendance requirement can still be met.

        Args:
            period: ReportingPeriod to check
            as_of_date: Date to calculate as of (defaults to today)

        Returns:
            True if requirement can still be met, False otherwise

        Implementation Notes:
            - Convenience method for checking achievability
            - Implements Requirement 4.6
        """
        status = self.calculate_compliance_status(period, as_of_date)
        return status.is_achievable

    def predict_compliance(
        self,
        period: ReportingPeriod,
        planned_in_office_dates: list[date],
        as_of_date: date | None = None
    ) -> ComplianceStatus:
        """
        Predict compliance status if planned in-office dates are followed.

        Args:
            period: ReportingPeriod to predict for
            planned_in_office_dates: List of future dates planned to be in-office
            as_of_date: Date to predict from (defaults to today)

        Returns:
            ComplianceStatus projected to end of period

        Implementation Notes:
            - Loads existing attendance records
            - Adds planned dates that fall on workdays within the period
            - Projects compliance status to period end date
            - Does not modify stored attendance data
            - Implements Requirements 8.1, 8.2, 8.3
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Get current status
        current_status = self.calculate_compliance_status(period, as_of_date)

        # Count additional in-office days from planned dates
        additional_days = 0
        for planned_date in planned_in_office_dates:
            # Only count dates in the future and within the period
            if planned_date > as_of_date and period.start_date <= planned_date <= period.end_date:
                # Only count if it's a workday
                if self._business_day_calc.is_workday(planned_date):
                    additional_days += 1

        # Project total in-office days
        projected_in_office_days = current_status.in_office_days + additional_days

        # Calculate projected remaining required
        projected_remaining_required = max(
            0,
            current_status.effective_required_days - projected_in_office_days
        )

        # For prediction, remaining workdays is 0 since we're projecting to end
        projected_remaining_workdays = 0

        # Determine projected compliance
        projected_is_compliant = projected_in_office_days >= current_status.effective_required_days
        projected_is_achievable = projected_remaining_required == 0

        # Calculate projected risk level
        projected_risk_level = self._calculate_risk_level(
            projected_remaining_required,
            projected_remaining_workdays,
            projected_is_compliant
        )

        return ComplianceStatus(
            period=period,
            as_of_date=period.end_date,  # Projection to end of period
            in_office_days=projected_in_office_days,
            effective_required_days=current_status.effective_required_days,
            remaining_required_days=projected_remaining_required,
            remaining_workdays=projected_remaining_workdays,
            risk_level=projected_risk_level,
            is_compliant=projected_is_compliant,
            is_achievable=projected_is_achievable
        )
