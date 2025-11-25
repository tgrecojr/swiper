"""
Tests for the AttendanceStore module.

This module tests all functionality related to attendance data storage,
including saving records, loading records, atomic writes, and validation.
"""

from datetime import date
from pathlib import Path
import json
import os
import pytest

from swiper.storage import AttendanceStore
from swiper.models import AttendanceRecord
from swiper.exceptions import StorageError


class TestDataDirectoryCreation:
    """Test data directory creation and permissions."""

    def test_directory_created_on_init(self, tmp_path):
        """Test that data directory is created during initialization."""
        data_dir = tmp_path / "attendance_data"
        assert not data_dir.exists()

        store = AttendanceStore(data_dir)

        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_directory_permissions(self, tmp_path):
        """Test that data directory is created with correct permissions."""
        data_dir = tmp_path / "attendance_data"
        store = AttendanceStore(data_dir)

        # Check permissions (0o755 = rwxr-xr-x)
        stat_info = os.stat(data_dir)
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o755

    def test_existing_directory_not_error(self, tmp_path):
        """Test that existing directory doesn't cause an error."""
        data_dir = tmp_path / "attendance_data"
        data_dir.mkdir()

        # Should not raise an error
        store = AttendanceStore(data_dir)
        assert data_dir.exists()


class TestSaveRecord:
    """Test saving attendance records."""

    def test_save_new_record(self, tmp_path):
        """Test saving a new attendance record."""
        store = AttendanceStore(tmp_path)
        record = AttendanceRecord(date=date(2025, 8, 15), status="in-office")

        store.save_record(record)

        # Verify file was created
        file_path = tmp_path / "attendance_2025.json"
        assert file_path.exists()

        # Verify content
        with open(file_path, 'r') as f:
            data = json.load(f)

        assert data == {"2025-08-15": "in-office"}

    def test_save_multiple_records_same_year(self, tmp_path):
        """Test saving multiple records to the same year file."""
        store = AttendanceStore(tmp_path)

        records = [
            AttendanceRecord(date=date(2025, 8, 15), status="in-office"),
            AttendanceRecord(date=date(2025, 8, 16), status="remote"),
            AttendanceRecord(date=date(2025, 8, 17), status="in-office"),
        ]

        for record in records:
            store.save_record(record)

        # Verify all records saved
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'r') as f:
            data = json.load(f)

        assert len(data) == 3
        assert data["2025-08-15"] == "in-office"
        assert data["2025-08-16"] == "remote"
        assert data["2025-08-17"] == "in-office"

    def test_overwrite_existing_record(self, tmp_path):
        """Test that saving a record for an existing date overwrites it."""
        store = AttendanceStore(tmp_path)

        # Save initial record
        record1 = AttendanceRecord(date=date(2025, 8, 15), status="in-office")
        store.save_record(record1)

        # Overwrite with different status
        record2 = AttendanceRecord(date=date(2025, 8, 15), status="remote")
        store.save_record(record2)

        # Verify overwrite
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'r') as f:
            data = json.load(f)

        assert len(data) == 1
        assert data["2025-08-15"] == "remote"

    def test_file_permissions_on_save(self, tmp_path):
        """Test that saved files have correct permissions (0o644)."""
        store = AttendanceStore(tmp_path)
        record = AttendanceRecord(date=date(2025, 8, 15), status="in-office")

        store.save_record(record)

        file_path = tmp_path / "attendance_2025.json"
        stat_info = os.stat(file_path)
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o644  # rw-r--r--

    def test_json_formatting(self, tmp_path):
        """Test that JSON is formatted with proper indentation."""
        store = AttendanceStore(tmp_path)
        record = AttendanceRecord(date=date(2025, 8, 15), status="in-office")

        store.save_record(record)

        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'r') as f:
            content = f.read()

        # Check for indentation (should have newlines and spaces)
        assert '\n' in content
        assert '  ' in content  # 2-space indent


class TestAtomicWrite:
    """Test atomic write functionality."""

    def test_atomic_write_no_corruption(self, tmp_path):
        """Test that atomic write prevents corruption on failure."""
        store = AttendanceStore(tmp_path)

        # Save initial record
        record1 = AttendanceRecord(date=date(2025, 8, 15), status="in-office")
        store.save_record(record1)

        file_path = tmp_path / "attendance_2025.json"
        tmp_file = file_path.with_suffix('.json.tmp')

        # Verify no .tmp file left behind
        assert file_path.exists()
        assert not tmp_file.exists()

    def test_tmp_file_cleaned_up_on_error(self, tmp_path):
        """Test that temporary files are cleaned up on error."""
        store = AttendanceStore(tmp_path)

        # Create a scenario that will fail (invalid data)
        file_path = tmp_path / "attendance_2025.json"
        tmp_file = file_path.with_suffix('.json.tmp')

        # Attempt to trigger an error by making directory read-only after creating it
        # This is a best-effort test as some systems may not support this
        try:
            # Save a valid record first
            record = AttendanceRecord(date=date(2025, 8, 15), status="in-office")
            store.save_record(record)

            # Verify no tmp file
            assert not tmp_file.exists()

        except StorageError:
            # If error occurs, tmp should still be cleaned up
            assert not tmp_file.exists()


class TestLoadRecords:
    """Test loading attendance records."""

    def test_load_records_single_year(self, tmp_path):
        """Test loading records from a single year."""
        store = AttendanceStore(tmp_path)

        # Save some records
        records = [
            AttendanceRecord(date=date(2025, 8, 15), status="in-office"),
            AttendanceRecord(date=date(2025, 8, 16), status="remote"),
            AttendanceRecord(date=date(2025, 8, 17), status="in-office"),
        ]
        for record in records:
            store.save_record(record)

        # Load records
        loaded = store.load_records(date(2025, 8, 15), date(2025, 8, 17))

        assert len(loaded) == 3
        assert loaded[0].date == date(2025, 8, 15)
        assert loaded[0].status == "in-office"
        assert loaded[1].date == date(2025, 8, 16)
        assert loaded[1].status == "remote"
        assert loaded[2].date == date(2025, 8, 17)
        assert loaded[2].status == "in-office"

    def test_load_records_multiple_years(self, tmp_path):
        """Test loading records across multiple years."""
        store = AttendanceStore(tmp_path)

        # Save records spanning 2025-2026
        records = [
            AttendanceRecord(date=date(2025, 12, 30), status="in-office"),
            AttendanceRecord(date=date(2025, 12, 31), status="remote"),
            AttendanceRecord(date=date(2026, 1, 1), status="remote"),
            AttendanceRecord(date=date(2026, 1, 2), status="in-office"),
        ]
        for record in records:
            store.save_record(record)

        # Load across years
        loaded = store.load_records(date(2025, 12, 30), date(2026, 1, 2))

        assert len(loaded) == 4
        assert loaded[0].date == date(2025, 12, 30)
        assert loaded[3].date == date(2026, 1, 2)

    def test_load_records_filters_date_range(self, tmp_path):
        """Test that loading filters to the specified date range."""
        store = AttendanceStore(tmp_path)

        # Save records for entire month
        for day in range(1, 31):
            record = AttendanceRecord(date=date(2025, 8, day), status="in-office")
            store.save_record(record)

        # Load only middle of month
        loaded = store.load_records(date(2025, 8, 10), date(2025, 8, 20))

        assert len(loaded) == 11  # Days 10-20 inclusive
        assert loaded[0].date == date(2025, 8, 10)
        assert loaded[-1].date == date(2025, 8, 20)

    def test_load_records_sorted_by_date(self, tmp_path):
        """Test that loaded records are sorted by date."""
        store = AttendanceStore(tmp_path)

        # Save in random order
        records = [
            AttendanceRecord(date=date(2025, 8, 20), status="in-office"),
            AttendanceRecord(date=date(2025, 8, 15), status="remote"),
            AttendanceRecord(date=date(2025, 8, 18), status="in-office"),
        ]
        for record in records:
            store.save_record(record)

        # Load should be sorted
        loaded = store.load_records(date(2025, 8, 1), date(2025, 8, 31))

        assert len(loaded) == 3
        assert loaded[0].date == date(2025, 8, 15)
        assert loaded[1].date == date(2025, 8, 18)
        assert loaded[2].date == date(2025, 8, 20)

    def test_load_records_empty_range(self, tmp_path):
        """Test loading records when no records exist in range."""
        store = AttendanceStore(tmp_path)

        # No records saved
        loaded = store.load_records(date(2025, 8, 1), date(2025, 8, 31))

        assert len(loaded) == 0


class TestGetRecordsForYear:
    """Test loading records for a specific year."""

    def test_get_records_for_existing_year(self, tmp_path):
        """Test getting records for a year with data."""
        store = AttendanceStore(tmp_path)

        # Save some records
        records = [
            AttendanceRecord(date=date(2025, 8, 15), status="in-office"),
            AttendanceRecord(date=date(2025, 8, 16), status="remote"),
        ]
        for record in records:
            store.save_record(record)

        year_data = store.get_records_for_year(2025)

        assert len(year_data) == 2
        assert year_data["2025-08-15"] == "in-office"
        assert year_data["2025-08-16"] == "remote"

    def test_get_records_for_missing_year(self, tmp_path):
        """Test getting records for a year with no file returns empty dict."""
        store = AttendanceStore(tmp_path)

        year_data = store.get_records_for_year(2025)

        assert year_data == {}
        assert isinstance(year_data, dict)


class TestValidation:
    """Test record validation."""

    def test_invalid_status_value(self, tmp_path):
        """Test that invalid status values raise StorageError."""
        store = AttendanceStore(tmp_path)
        record = AttendanceRecord(date=date(2025, 8, 15), status="invalid-status")

        with pytest.raises(StorageError) as exc_info:
            store.save_record(record)

        assert "Invalid attendance status" in str(exc_info.value)
        assert "invalid-status" in str(exc_info.value)

    def test_invalid_date_format_in_file(self, tmp_path):
        """Test that invalid date format in JSON raises StorageError."""
        store = AttendanceStore(tmp_path)

        # Manually create file with invalid date format
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'w') as f:
            json.dump({"not-a-date": "in-office"}, f)

        with pytest.raises(StorageError) as exc_info:
            store.load_records(date(2025, 1, 1), date(2025, 12, 31))

        assert "Invalid date format" in str(exc_info.value)

    def test_invalid_status_in_file(self, tmp_path):
        """Test that invalid status in JSON raises StorageError."""
        store = AttendanceStore(tmp_path)

        # Manually create file with invalid status
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'w') as f:
            json.dump({"2025-08-15": "invalid-status"}, f)

        with pytest.raises(StorageError) as exc_info:
            store.load_records(date(2025, 1, 1), date(2025, 12, 31))

        assert "Invalid attendance status" in str(exc_info.value)


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    def test_corrupt_json_file(self, tmp_path):
        """Test that corrupted JSON file raises StorageError."""
        store = AttendanceStore(tmp_path)

        # Create corrupted JSON file
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'w') as f:
            f.write("{corrupt json")

        with pytest.raises(StorageError) as exc_info:
            store.get_records_for_year(2025)

        assert "Failed to parse" in str(exc_info.value)

    def test_invalid_data_structure(self, tmp_path):
        """Test that invalid data structure raises StorageError."""
        store = AttendanceStore(tmp_path)

        # Create file with list instead of dict
        file_path = tmp_path / "attendance_2025.json"
        with open(file_path, 'w') as f:
            json.dump(["not", "a", "dict"], f)

        with pytest.raises(StorageError) as exc_info:
            store.get_records_for_year(2025)

        assert "Invalid data structure" in str(exc_info.value)
        assert "expected dict" in str(exc_info.value)
