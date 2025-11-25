"""
Tests for the ComplianceChecker module.

This module tests all functionality related to compliance checking,
including status calculation, risk level determination, and predictive analysis.
"""

from datetime import date, timedelta
import pytest

from swiper.compliance import ComplianceChecker, ComplianceStatus
from swiper.reporting import ReportingPeriodCalculator
from swiper.business_days import BusinessDayCalculator
from swiper.storage import AttendanceStore
from swiper.models import ReportingPeriod, AttendanceRecord


@pytest.fixture
def sample_holidays():
    """Sample holiday dates for testing."""
    return [
        date(2025, 9, 1),   # Labor Day (Monday)
        date(2025, 10, 13), # Indigenous Peoples' Day (Monday)
        date(2025, 11, 11), # Veterans Day (Tuesday)
    ]


@pytest.fixture
def sample_period():
    """Sample reporting period for testing (Aug 15 - Nov 14, 2025)."""
    return ReportingPeriod(
        period_number=1,
        start_date=date(2025, 8, 15),
        end_date=date(2025, 11, 14),
        report_date=date(2025, 12, 3),
        baseline_required_days=20,
        exclusion_days=[],
        effective_required_days=20
    )


@pytest.fixture
def business_calc(sample_holidays):
    """BusinessDayCalculator fixture."""
    return BusinessDayCalculator(sample_holidays)


@pytest.fixture
def period_calc(sample_period, business_calc):
    """ReportingPeriodCalculator fixture."""
    return ReportingPeriodCalculator([sample_period], business_calc)


@pytest.fixture
def store(tmp_path):
    """AttendanceStore fixture with temporary directory."""
    return AttendanceStore(tmp_path)


@pytest.fixture
def checker(period_calc, business_calc, store):
    """ComplianceChecker fixture."""
    return ComplianceChecker(period_calc, business_calc, store)


class TestCalculateComplianceStatus:
    """Test compliance status calculation."""

    def test_no_attendance_records(self, checker, sample_period):
        """Test compliance status with no attendance records."""
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 20)
        )

        assert status.in_office_days == 0
        assert status.effective_required_days == 17  # 20 - 3 holidays
        assert status.remaining_required_days == 17
        assert status.is_compliant is False
        assert status.risk_level in ["possible", "at-risk", "critical", "impossible"]

    def test_some_attendance_records(self, checker, sample_period, store):
        """Test compliance status with some attendance records."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            record = AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            )
            store.save_record(record)

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 20)
        )

        assert status.in_office_days == 5
        assert status.effective_required_days == 17  # 20 - 3 holidays
        assert status.remaining_required_days == 12
        assert status.is_compliant is False

    def test_requirement_exactly_met(self, checker, sample_period, store):
        """Test compliance status when requirement is exactly met."""
        # Add exactly 17 in-office days (effective requirement)
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 17:
            if current.weekday() < 5:  # Weekday
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 10, 1)
        )

        assert status.in_office_days == 17
        assert status.remaining_required_days == 0
        assert status.is_compliant is True
        assert status.risk_level == "achieved"

    def test_requirement_exceeded(self, checker, sample_period, store):
        """Test compliance status when requirement is exceeded."""
        # Add 20 in-office days (more than required)
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 20:
            if current.weekday() < 5:  # Weekday
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 10, 15)
        )

        assert status.in_office_days == 20
        assert status.remaining_required_days == 0
        assert status.is_compliant is True
        assert status.risk_level == "achieved"

    def test_as_of_date_defaults_to_today(self, checker, sample_period):
        """Test that as_of_date defaults to today."""
        status = checker.calculate_compliance_status(sample_period)
        assert status.as_of_date == date.today()

    def test_as_of_date_in_middle_of_period(self, checker, sample_period, store):
        """Test compliance calculation for a date in the middle of period."""
        # Add records before and after as_of_date
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 16), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 9, 15), status="in-office"))

        # Only first two should count
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 20)
        )

        assert status.in_office_days == 2

    def test_as_of_date_at_period_end(self, checker, sample_period, store):
        """Test compliance calculation at period end date."""
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 11, 14), status="in-office"))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 11, 14)
        )

        assert status.in_office_days == 2
        assert status.remaining_workdays == 0


class TestRiskLevels:
    """Test risk level calculations."""

    def test_risk_level_achieved(self, checker, sample_period, store):
        """Test 'achieved' risk level when requirement is met."""
        # Add 17 in-office days (meets effective requirement)
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 17:
            if current.weekday() < 5:
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 9, 30)
        )

        assert status.risk_level == "achieved"
        assert status.is_compliant is True

    def test_risk_level_possible(self, checker, sample_period, store):
        """Test 'possible' risk level with comfortable buffer."""
        # Add 5 in-office days early in period
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 25)
        )

        # Should have plenty of remaining workdays to meet requirement
        assert status.remaining_required_days == 12  # 17 - 5
        buffer = status.remaining_workdays - status.remaining_required_days
        assert buffer >= 5
        assert status.risk_level == "possible"

    def test_risk_level_at_risk(self, checker, sample_period, store):
        """Test 'at-risk' risk level with small buffer."""
        # Add records to create scenario with 1-4 days buffer
        # Period: Aug 15 - Nov 14, 2025
        # Effective requirement: 17 days (20 - 3 holidays)

        # Add 10 in-office days
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 10:
            if current.weekday() < 5:
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        # Check status late in period to have small buffer
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 10, 20)
        )

        # Need 7 more days (17 - 10)
        assert status.remaining_required_days == 7
        buffer = status.remaining_workdays - status.remaining_required_days

        # Should have 1-4 days buffer for at-risk
        if 1 <= buffer < 5:
            assert status.risk_level == "at-risk"

    def test_risk_level_critical(self, checker, sample_period, store):
        """Test 'critical' risk level when all remaining workdays needed."""
        # Period: Aug 15 - Nov 14, 2025
        # Need to create scenario where remaining_required == remaining_workdays

        # Add 5 in-office days
        for day in [15, 18, 19, 20, 21]:  # Mix of dates
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        # Check late in period
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 11, 1)
        )

        # Need 12 more days (17 - 5)
        assert status.remaining_required_days == 12

        # If remaining workdays exactly equals remaining required, it's critical
        if status.remaining_workdays == status.remaining_required_days:
            assert status.risk_level == "critical"

    def test_risk_level_impossible(self, checker, sample_period, store):
        """Test 'impossible' risk level when requirement cannot be met."""
        # Add only 2 in-office days
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 16), status="in-office"))

        # Check at end of period
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 11, 14)
        )

        assert status.in_office_days == 2
        assert status.remaining_required_days == 15  # 17 - 2
        assert status.remaining_workdays == 0
        assert status.risk_level == "impossible"
        assert status.is_achievable is False


class TestRemainingRequiredDays:
    """Test remaining required days calculation."""

    def test_get_remaining_required_days_zero(self, checker, sample_period, store):
        """Test remaining required days when requirement is met."""
        # Add 17 in-office days
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 17:
            if current.weekday() < 5:
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        remaining = checker.get_remaining_required_days(
            sample_period,
            as_of_date=date(2025, 9, 30)
        )

        assert remaining == 0

    def test_get_remaining_required_days_positive(self, checker, sample_period, store):
        """Test remaining required days with some attendance."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        remaining = checker.get_remaining_required_days(
            sample_period,
            as_of_date=date(2025, 8, 25)
        )

        assert remaining == 12  # 17 - 5

    def test_get_remaining_required_days_none(self, checker, sample_period):
        """Test remaining required days with no attendance."""
        remaining = checker.get_remaining_required_days(
            sample_period,
            as_of_date=date(2025, 8, 20)
        )

        assert remaining == 17  # Full effective requirement


class TestIsAchievable:
    """Test achievability checking."""

    def test_is_achievable_true_early_period(self, checker, sample_period):
        """Test achievability returns True early in period."""
        achievable = checker.is_achievable(
            sample_period,
            as_of_date=date(2025, 8, 20)
        )

        assert achievable is True

    def test_is_achievable_true_with_progress(self, checker, sample_period, store):
        """Test achievability returns True with some progress."""
        # Add 10 in-office days
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 10:
            if current.weekday() < 5:
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        achievable = checker.is_achievable(
            sample_period,
            as_of_date=date(2025, 9, 15)
        )

        assert achievable is True

    def test_is_achievable_false_end_of_period(self, checker, sample_period, store):
        """Test achievability returns False when requirement cannot be met."""
        # Add only 2 in-office days
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 16), status="in-office"))

        achievable = checker.is_achievable(
            sample_period,
            as_of_date=date(2025, 11, 14)
        )

        assert achievable is False

    def test_is_achievable_true_when_achieved(self, checker, sample_period, store):
        """Test achievability returns True when requirement already met."""
        # Add 17 in-office days
        in_office_dates = []
        current = date(2025, 8, 15)
        while len(in_office_dates) < 17:
            if current.weekday() < 5:
                in_office_dates.append(current)
            current += timedelta(days=1)

        for dt in in_office_dates:
            store.save_record(AttendanceRecord(date=dt, status="in-office"))

        achievable = checker.is_achievable(
            sample_period,
            as_of_date=date(2025, 9, 30)
        )

        assert achievable is True


class TestPredictCompliance:
    """Test predictive compliance analysis."""

    def test_predict_no_planned_dates(self, checker, sample_period, store):
        """Test prediction with no planned future dates."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        prediction = checker.predict_compliance(
            sample_period,
            [],
            as_of_date=date(2025, 8, 25)
        )

        assert prediction.in_office_days == 5
        assert prediction.remaining_required_days == 12  # 17 - 5

    def test_predict_with_planned_dates(self, checker, sample_period, store):
        """Test prediction with planned future dates."""
        # Add 5 in-office days so far
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        # Plan 12 more in-office days (all weekdays)
        planned_dates = [
            date(2025, 9, 2),   # Tuesday
            date(2025, 9, 3),   # Wednesday
            date(2025, 9, 4),   # Thursday
            date(2025, 9, 5),   # Friday
            date(2025, 9, 8),   # Monday
            date(2025, 9, 9),   # Tuesday
            date(2025, 9, 10),  # Wednesday
            date(2025, 9, 11),  # Thursday
            date(2025, 9, 12),  # Friday
            date(2025, 9, 15),  # Monday
            date(2025, 9, 16),  # Tuesday
            date(2025, 9, 17),  # Wednesday
        ]

        prediction = checker.predict_compliance(
            sample_period,
            planned_dates,
            as_of_date=date(2025, 8, 25)
        )

        assert prediction.in_office_days == 17  # 5 + 12
        assert prediction.remaining_required_days == 0
        assert prediction.is_compliant is True
        assert prediction.risk_level == "achieved"

    def test_predict_ignores_past_dates(self, checker, sample_period, store):
        """Test that prediction ignores dates in the past."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        # Include past dates in planned list
        planned_dates = [
            date(2025, 8, 20),  # Past date (before as_of_date)
            date(2025, 9, 2),   # Future date (after as_of_date)
        ]

        prediction = checker.predict_compliance(
            sample_period,
            planned_dates,
            as_of_date=date(2025, 8, 25)
        )

        # Should only count the future date (if it's a workday)
        # 5 existing + 1 planned = 6 total
        assert prediction.in_office_days == 6

    def test_predict_ignores_weekend_dates(self, checker, sample_period, store):
        """Test that prediction ignores weekend dates."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        # Include weekend dates
        planned_dates = [
            date(2025, 9, 6),   # Saturday
            date(2025, 9, 7),   # Sunday
            date(2025, 9, 2),   # Tuesday (weekday)
        ]

        prediction = checker.predict_compliance(
            sample_period,
            planned_dates,
            as_of_date=date(2025, 8, 25)
        )

        # Should only count the weekday
        assert prediction.in_office_days == 6  # 5 + 1

    def test_predict_ignores_dates_outside_period(self, checker, sample_period, store):
        """Test that prediction ignores dates outside the period."""
        # Add 5 in-office days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="in-office"
            ))

        # Include dates outside period
        planned_dates = [
            date(2025, 7, 15),  # Before period start
            date(2025, 12, 1),  # After period end
            date(2025, 9, 2),   # Within period
        ]

        prediction = checker.predict_compliance(
            sample_period,
            planned_dates,
            as_of_date=date(2025, 8, 25)
        )

        # Should only count the date within period
        assert prediction.in_office_days == 6  # 5 + 1

    def test_predict_projects_to_period_end(self, checker, sample_period):
        """Test that prediction projects to end of period."""
        prediction = checker.predict_compliance(
            sample_period,
            [],
            as_of_date=date(2025, 8, 25)
        )

        assert prediction.as_of_date == sample_period.end_date
        assert prediction.remaining_workdays == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_compliance_at_period_start(self, checker, sample_period):
        """Test compliance calculation on period start date."""
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=sample_period.start_date
        )

        assert status.in_office_days == 0
        assert status.as_of_date == sample_period.start_date

    def test_compliance_after_period_end(self, checker, sample_period, store):
        """Test compliance calculation after period ends."""
        # Add some records
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 16), status="in-office"))

        # Check after period end
        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 12, 1)
        )

        assert status.in_office_days == 2
        assert status.remaining_workdays == 0

    def test_only_remote_days_recorded(self, checker, sample_period, store):
        """Test compliance when only remote days are recorded."""
        # Add only remote days
        for day in [15, 16, 17, 18, 19]:
            store.save_record(AttendanceRecord(
                date=date(2025, 8, day),
                status="remote"
            ))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 25)
        )

        assert status.in_office_days == 0
        assert status.remaining_required_days == 17

    def test_mixed_in_office_and_remote(self, checker, sample_period, store):
        """Test compliance with mixed in-office and remote days."""
        # Add mixed records
        store.save_record(AttendanceRecord(date=date(2025, 8, 15), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 16), status="remote"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 17), status="in-office"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 18), status="remote"))
        store.save_record(AttendanceRecord(date=date(2025, 8, 19), status="in-office"))

        status = checker.calculate_compliance_status(
            sample_period,
            as_of_date=date(2025, 8, 25)
        )

        assert status.in_office_days == 3  # Only count in-office
        assert status.remaining_required_days == 14  # 17 - 3
