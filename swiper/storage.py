"""
Attendance data storage for the Swiper application.

This module provides the AttendanceStore class for persisting and retrieving
attendance records using file-based JSON storage with atomic writes.
"""

import json
import os
from pathlib import Path
from datetime import date
from typing import Dict

from swiper.models import AttendanceRecord
from swiper.exceptions import StorageError


class AttendanceStore:
    """
    Manages file-based storage of attendance records using JSON.

    Stores attendance data in yearly JSON files (attendance_YYYY.json) with
    atomic writes to prevent corruption. Each file contains a dictionary mapping
    date strings to attendance status values.

    Attributes:
        _data_dir: Path to the directory containing attendance data files
    """

    def __init__(self, data_dir: Path):
        """
        Initialize the AttendanceStore with a data directory.

        Args:
            data_dir: Path to directory where attendance files will be stored

        Implementation Notes:
            - Creates the data directory if it doesn't exist
            - Implements Requirement 2.6
        """
        self._data_dir = Path(data_dir)
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """
        Ensure the data directory exists with correct permissions.

        Creates the directory if it doesn't exist, including parent directories.
        Sets permissions to 0o755 (rwxr-xr-x).

        Implementation Notes:
            - Uses os.makedirs with exist_ok=True for idempotency
            - Implements Requirement 10.2
        """
        os.makedirs(self._data_dir, mode=0o755, exist_ok=True)

    def _get_year_file_path(self, year: int) -> Path:
        """
        Get the file path for a specific year's attendance data.

        Args:
            year: Year for which to get the file path

        Returns:
            Path object for the year file (e.g., data/attendance_2025.json)

        Implementation Notes:
            - File naming convention: attendance_YYYY.json
            - Implements Requirement 2.7
        """
        return self._data_dir / f"attendance_{year}.json"

    def _atomic_write(self, file_path: Path, data: Dict[str, str]) -> None:
        """
        Atomically write data to a JSON file.

        Writes to a temporary file first, then renames to the target file.
        This prevents corruption if the write is interrupted.

        Args:
            file_path: Target file path
            data: Dictionary to write as JSON

        Raises:
            StorageError: If write or rename operations fail

        Implementation Notes:
            - Writes to {file_path}.tmp first
            - Uses os.rename() for atomic operation
            - Sets file permissions to 0o644 (rw-r--r--)
            - JSON formatted with indent=2 for readability
            - Implements Requirements 2.8, 11.1, 11.2
        """
        tmp_path = file_path.with_suffix('.json.tmp')

        try:
            # Write to temporary file
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2, sort_keys=True)

            # Set file permissions
            os.chmod(tmp_path, 0o644)

            # Atomically rename to final location
            os.rename(tmp_path, file_path)

        except (IOError, OSError) as e:
            # Clean up temporary file if it exists
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise StorageError(f"Failed to write to {file_path}: {e}")

    def _validate_record_data(self, record_date: date, status: str) -> None:
        """
        Validate attendance record data before storage.

        Args:
            record_date: Date of the attendance record
            status: Attendance status value

        Raises:
            StorageError: If validation fails

        Implementation Notes:
            - Validates status is either "in-office" or "remote"
            - Implements Requirements 11.3, 11.4
        """
        valid_statuses = {"in-office", "remote"}
        if status not in valid_statuses:
            raise StorageError(
                f"Invalid attendance status: '{status}'. "
                f"Must be one of: {', '.join(sorted(valid_statuses))}"
            )

    def save_record(self, record: AttendanceRecord) -> None:
        """
        Save an attendance record to storage.

        If a record for the same date already exists, it will be overwritten.
        Uses atomic write to prevent corruption.

        Args:
            record: AttendanceRecord instance to save

        Raises:
            StorageError: If save operation fails or validation fails

        Implementation Notes:
            - Loads existing year data if present
            - Updates with new record
            - Writes atomically
            - Implements Requirements 2.6, 2.9, 11.5
        """
        # Validate record data
        self._validate_record_data(record.date, record.status)

        year = record.date.year
        file_path = self._get_year_file_path(year)

        # Load existing data for this year
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    year_data = json.load(f)
            except json.JSONDecodeError as e:
                raise StorageError(f"Failed to parse {file_path}: {e}")
            except IOError as e:
                raise StorageError(f"Failed to read {file_path}: {e}")
        else:
            year_data = {}

        # Update with new record
        date_str = record.date.isoformat()
        year_data[date_str] = record.status

        # Write atomically
        self._atomic_write(file_path, year_data)

    def get_records_for_year(self, year: int) -> Dict[str, str]:
        """
        Load all attendance records for a specific year.

        Args:
            year: Year for which to load records

        Returns:
            Dictionary mapping date strings (YYYY-MM-DD) to status values.
            Returns empty dict if file doesn't exist.

        Raises:
            StorageError: If file exists but cannot be parsed

        Implementation Notes:
            - Returns empty dict for missing files (not an error)
            - Validates JSON structure
            - Implements Requirements 2.10, 11.6
        """
        file_path = self._get_year_file_path(year)

        # Missing file is not an error
        if not file_path.exists():
            return {}

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Validate it's a dictionary
            if not isinstance(data, dict):
                raise StorageError(
                    f"Invalid data structure in {file_path}: expected dict, got {type(data).__name__}"
                )

            return data

        except json.JSONDecodeError as e:
            raise StorageError(f"Failed to parse {file_path}: {e}")
        except IOError as e:
            raise StorageError(f"Failed to read {file_path}: {e}")

    def load_records(self, start_date: date, end_date: date) -> list[AttendanceRecord]:
        """
        Load attendance records for a date range.

        Args:
            start_date: First date of range (inclusive)
            end_date: Last date of range (inclusive)

        Returns:
            List of AttendanceRecord instances within the date range,
            sorted by date

        Raises:
            StorageError: If file parsing fails

        Implementation Notes:
            - Loads data from all necessary year files
            - Filters to date range
            - Validates date formats and status values
            - Returns empty list if no records found
            - Implements Requirements 2.10, 6.1
        """
        records: list[AttendanceRecord] = []

        # Determine which years we need to load
        start_year = start_date.year
        end_year = end_date.year

        # Load records from all relevant years
        for year in range(start_year, end_year + 1):
            year_data = self.get_records_for_year(year)

            for date_str, status in year_data.items():
                # Parse date
                try:
                    record_date = date.fromisoformat(date_str)
                except ValueError as e:
                    raise StorageError(
                        f"Invalid date format in year {year} data: '{date_str}'. Error: {e}"
                    )

                # Validate status
                self._validate_record_data(record_date, status)

                # Filter to date range
                if start_date <= record_date <= end_date:
                    records.append(AttendanceRecord(date=record_date, status=status))

        # Sort by date
        records.sort(key=lambda r: r.date)

        return records
