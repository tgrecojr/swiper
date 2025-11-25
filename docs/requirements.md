# Requirements Document

## Introduction

This document defines the functional requirements for the In-Office Attendance Tracking Application. Each requirement is decomposed into specific, testable acceptance criteria assigned to system components defined in the architectural blueprint.

## Glossary

- **Workday**: A weekday (Monday-Friday) that is not an exclusion day
- **Exclusion Day**: A holiday or company shutdown day that does not count toward attendance requirements
- **Reporting Period**: A 13-week span with defined start date, end date, and reporting deadline
- **In-Office Day**: A workday where the employee is physically present at the office
- **Remote Day**: A workday where the employee works from home
- **Effective Required Days**: Baseline required in-office days minus exclusion days within the reporting period
- **Compliance**: Meeting or exceeding the effective required in-office days for a reporting period

## Requirements

### Requirement 1: Configuration Loading and Validation

The system shall load all configuration from TOML and YAML files, validate structure and data types, and provide meaningful error messages for invalid configurations.

#### Acceptance Criteria

1.1. WHEN the application starts, THE **ConfigurationManager** SHALL attempt to load the main configuration file from `config/config.toml`.

1.2. WHEN the main configuration file is missing, THE **ConfigurationManager** SHALL raise a ConfigurationError with the message "Configuration file not found: config/config.toml".

1.3. WHEN the main configuration file contains invalid TOML syntax, THE **ConfigurationManager** SHALL raise a ConfigurationError with line number and syntax details.

1.4. WHEN the main configuration file is loaded successfully, THE **ConfigurationManager** SHALL validate the structure using Pydantic models enforcing required fields: `policy.required_days_per_period` (integer), `policy.period_length_weeks` (integer), `data.reporting_periods_file` (string), `data.exclusion_days_file` (string), and `data.attendance_data_dir` (string).

1.5. WHEN any required configuration field is missing or has an invalid type, THE **ConfigurationManager** SHALL raise a ConfigurationError listing all validation failures.

1.6. WHEN the reporting periods file path is specified in config, THE **ConfigurationManager** SHALL load and parse the TOML file containing reporting period definitions.

1.7. WHEN a reporting period definition is missing required fields (period_number, start_date, end_date, or deadline), THE **ConfigurationManager** SHALL raise a ConfigurationError identifying the invalid period.

1.8. WHEN the exclusion days file path is specified in config, THE **ConfigurationManager** SHALL load and parse the YAML file containing holiday calendar definitions.

1.9. WHEN all configuration files are loaded successfully, THE **ConfigurationManager** SHALL provide access methods returning validated Python dataclass instances for settings, reporting periods, and exclusion days.

### Requirement 2: Attendance Recording

The system shall allow users to record their attendance status (in-office or remote) for workdays, storing data in JSON files organized by year.

#### Acceptance Criteria

2.1. WHEN the user executes `swiper record in-office` without a date argument, THE **CLIInterface** SHALL record attendance as "in-office" for today's date.

2.2. WHEN the user executes `swiper record remote` without a date argument, THE **CLIInterface** SHALL record attendance as "remote" for today's date.

2.3. WHEN the user executes `swiper record in-office --date 2025-08-15`, THE **CLIInterface** SHALL record attendance as "in-office" for August 15, 2025.

2.4. WHEN the user provides a date argument, THE **CLIInterface** SHALL validate the date format is ISO 8601 (YYYY-MM-DD) and raise an error for invalid formats.

2.5. WHEN the user attempts to record attendance for a future date beyond today, THE **CLIInterface** SHALL reject the command with the error message "Cannot record attendance for future dates".

2.6. WHEN the **CLIInterface** receives a valid record command, THE **AttendanceStore** SHALL save the attendance record to the appropriate JSON file based on the year (`data/attendance_YYYY.json`).

2.7. WHEN the attendance data directory does not exist, THE **AttendanceStore** SHALL create the directory before saving data.

2.8. WHEN the JSON file for the year does not exist, THE **AttendanceStore** SHALL create a new JSON file with an empty object structure.

2.9. WHEN an attendance record already exists for a specific date, THE **AttendanceStore** SHALL overwrite the previous record with the new status without raising an error.

2.10. WHEN saving attendance data, THE **AttendanceStore** SHALL format the JSON file with proper indentation for human readability.

2.11. WHEN recording attendance is successful, THE **CLIInterface** SHALL display a confirmation message: "Recorded [status] for [date]".

### Requirement 3: Reporting Period Determination

The system shall identify which reporting period contains any given date and provide access to period details including start date, end date, and deadline.

#### Acceptance Criteria

3.1. WHEN given a date, THE **ReportingPeriodCalculator** SHALL return the ReportingPeriod that contains that date based on configured period definitions.

3.2. WHEN a date falls outside all defined reporting periods, THE **ReportingPeriodCalculator** SHALL raise a ValidationError with the message "No reporting period defined for date [date]".

3.3. WHEN multiple reporting periods are configured, THE **ReportingPeriodCalculator** SHALL correctly identify the period by checking if the date falls between start_date (inclusive) and end_date (inclusive).

3.4. WHEN the current date is requested, THE **ReportingPeriodCalculator** SHALL return the reporting period containing today's date.

3.5. WHEN period information is retrieved, THE **ReportingPeriodCalculator** SHALL return a ReportingPeriod dataclass containing period_number, start_date, end_date, deadline, and baseline_required_days.

### Requirement 4: Business Day Calculations

The system shall accurately calculate business days by excluding weekends and exclusion days from date ranges.

#### Acceptance Criteria

4.1. WHEN given a date, THE **BusinessDayCalculator** SHALL return True if the date is a weekday (Monday-Friday) and False otherwise.

4.2. WHEN given a date, THE **BusinessDayCalculator** SHALL return True if the date is an exclusion day (holiday) as defined in the holiday calendar configuration.

4.3. WHEN given a date, THE **BusinessDayCalculator** SHALL return True if the date is a workday (weekday AND not an exclusion day).

4.4. WHEN given a start date and end date, THE **BusinessDayCalculator** SHALL count the total number of workdays in the date range (inclusive of both start and end dates).

4.5. WHEN counting workdays, THE **BusinessDayCalculator** SHALL exclude Saturdays (weekday 5) and Sundays (weekday 6) from the count.

4.6. WHEN counting workdays, THE **BusinessDayCalculator** SHALL exclude any dates that match exclusion days from the holiday calendar.

4.7. WHEN given an exclusion day list and a reporting period, THE **BusinessDayCalculator** SHALL return only those exclusion days that fall within the period's start and end dates (inclusive).

### Requirement 5: Effective Required Days Calculation

The system shall calculate the effective required in-office days for each reporting period by subtracting exclusion days that fall within the period from the baseline requirement.

#### Acceptance Criteria

5.1. WHEN a reporting period is analyzed, THE **ReportingPeriodCalculator** SHALL retrieve all exclusion days from the **ConfigurationManager**.

5.2. WHEN a reporting period is analyzed, THE **ReportingPeriodCalculator** SHALL use the **BusinessDayCalculator** to identify which exclusion days fall within the period's date range.

5.3. WHEN a reporting period is analyzed, THE **ReportingPeriodCalculator** SHALL count exclusion days that are also weekdays (Monday-Friday) within the period.

5.4. WHEN calculating effective required days, THE **ReportingPeriodCalculator** SHALL subtract the count of weekday exclusion days from the baseline required days configured in settings.

5.5. WHEN the effective required days calculation results in a negative number, THE **ReportingPeriodCalculator** SHALL return zero as the minimum effective requirement.

5.6. WHEN the effective required days are calculated, THE **ReportingPeriodCalculator** SHALL return a ReportingPeriod dataclass with both baseline_required_days and effective_required_days populated.

### Requirement 6: Compliance Status Evaluation

The system shall evaluate whether the user has met the in-office attendance requirements for a reporting period and calculate remaining days needed.

#### Acceptance Criteria

6.1. WHEN compliance is checked for a reporting period, THE **ComplianceChecker** SHALL retrieve all attendance records for dates within the period from the **AttendanceStore**.

6.2. WHEN compliance is checked, THE **ComplianceChecker** SHALL count the number of dates marked as "in-office" within the reporting period.

6.3. WHEN compliance is checked, THE **ComplianceChecker** SHALL retrieve the effective required days for the period from the **ReportingPeriodCalculator**.

6.4. WHEN the in-office day count meets or exceeds the effective required days, THE **ComplianceChecker** SHALL set the is_compliant field to True in the ComplianceStatus dataclass.

6.5. WHEN the in-office day count is less than the effective required days, THE **ComplianceChecker** SHALL set the is_compliant field to False and calculate days_short as the difference.

6.6. WHEN the in-office day count exceeds the effective required days, THE **ComplianceChecker** SHALL calculate days_ahead as the surplus.

6.7. WHEN compliance is checked, THE **ComplianceChecker** SHALL use the **BusinessDayCalculator** to count remaining workdays from today's date through the end of the reporting period.

6.8. WHEN compliance is checked, THE **ComplianceChecker** SHALL return a ComplianceStatus dataclass containing: period reference, in_office_count, required_count (effective), workdays_remaining, is_compliant, days_short, and days_ahead.

### Requirement 7: Status Command

The system shall provide a status command that displays the current reporting period's compliance information in a user-friendly format.

#### Acceptance Criteria

7.1. WHEN the user executes `swiper status`, THE **CLIInterface** SHALL determine the current reporting period using the **ReportingPeriodCalculator**.

7.2. WHEN the user executes `swiper status`, THE **CLIInterface** SHALL request compliance evaluation for the current period from the **ComplianceChecker**.

7.3. WHEN displaying status, THE **CLIInterface** SHALL show the reporting period number, start date, end date, and deadline in readable format.

7.4. WHEN displaying status, THE **CLIInterface** SHALL show the baseline required days and the effective required days (after exclusions).

7.5. WHEN displaying status, THE **CLIInterface** SHALL show the count of in-office days recorded so far.

7.6. WHEN displaying status, THE **CLIInterface** SHALL show the number of remaining required days (effective_required - in_office_count, minimum 0).

7.7. WHEN displaying status, THE **CLIInterface** SHALL show the number of workdays remaining in the period.

7.8. WHEN the user is compliant, THE **CLIInterface** SHALL display "Status: Compliant" with days_ahead if applicable.

7.9. WHEN the user is not compliant, THE **CLIInterface** SHALL display "Status: Not Compliant" with days_short.

7.10. WHEN the user is not compliant but has enough remaining workdays, THE **CLIInterface** SHALL display "Status: On Track" instead.

### Requirement 8: Report Command

The system shall provide a report command that displays detailed attendance information for one or all reporting periods.

#### Acceptance Criteria

8.1. WHEN the user executes `swiper report` without arguments, THE **CLIInterface** SHALL generate a report for the current reporting period.

8.2. WHEN the user executes `swiper report --period N`, THE **CLIInterface** SHALL generate a report for reporting period number N.

8.3. WHEN the user executes `swiper report --all`, THE **CLIInterface** SHALL generate reports for all configured reporting periods.

8.4. WHEN the user specifies an invalid period number, THE **CLIInterface** SHALL display an error message "Invalid period number: [N]".

8.5. WHEN generating a report, THE **CLIInterface** SHALL display the period details: number, dates, deadline, baseline required days, effective required days, and exclusion day count.

8.6. WHEN generating a report, THE **CLIInterface** SHALL display compliance status from the **ComplianceChecker**.

8.7. WHEN generating a report with --all flag, THE **CLIInterface** SHALL iterate through all periods and display each report separated by blank lines.

### Requirement 9: Config Command

The system shall provide a config command to display and validate configuration settings.

#### Acceptance Criteria

9.1. WHEN the user executes `swiper config show`, THE **CLIInterface** SHALL display all current configuration settings including policy parameters and file paths.

9.2. WHEN the user executes `swiper config validate`, THE **CLIInterface** SHALL request validation from the **ConfigurationManager** for all configuration files.

9.3. WHEN configuration validation succeeds, THE **CLIInterface** SHALL display "Configuration valid" with counts of loaded periods and exclusion days.

9.4. WHEN configuration validation fails, THE **CLIInterface** SHALL display all validation errors with file names and line numbers where applicable.

### Requirement 10: Error Handling and User Experience

The system shall provide clear, actionable error messages and handle all edge cases gracefully.

#### Acceptance Criteria

10.1. WHEN any component raises a custom exception (ConfigurationError, StorageError, ValidationError), THE **CLIInterface** SHALL catch the exception and display a user-friendly error message.

10.2. WHEN a file I/O error occurs, THE **AttendanceStore** SHALL raise a StorageError with details about the file path and operation that failed.

10.3. WHEN JSON parsing fails on an attendance file, THE **AttendanceStore** SHALL raise a StorageError with the file path and parsing error details.

10.4. WHEN the user provides an unrecognized command, THE **CLIInterface** SHALL display available commands and usage information.

10.5. WHEN the user provides invalid arguments to a command, THE **CLIInterface** SHALL display command-specific help text with examples.

10.6. WHEN the application starts and configuration is invalid, THE **CLIInterface** SHALL exit with a non-zero status code after displaying errors.

10.7. WHEN any operation completes successfully, THE **CLIInterface** SHALL exit with status code 0.

### Requirement 11: Data Integrity and File Management

The system shall maintain data integrity and handle file operations safely.

#### Acceptance Criteria

11.1. WHEN writing to JSON files, THE **AttendanceStore** SHALL use atomic write operations (write to temporary file, then rename) to prevent data corruption on failure.

11.2. WHEN loading JSON files, THE **AttendanceStore** SHALL validate that all date keys are properly formatted ISO 8601 dates.

11.3. WHEN loading JSON files, THE **AttendanceStore** SHALL validate that all status values are either "in-office" or "remote".

11.4. WHEN invalid data is found in JSON files, THE **AttendanceStore** SHALL raise a StorageError identifying the invalid entries.

11.5. WHEN the attendance data directory is specified with a relative path, THE **AttendanceStore** SHALL resolve it relative to the project root directory.

11.6. WHEN the **AttendanceStore** creates directories, THE **AttendanceStore** SHALL set appropriate file permissions (755 for directories, 644 for files).

### Requirement 12: Predictive Compliance Analysis

The system shall predict and warn users when compliance is impossible or at risk based on remaining workdays in the reporting period.

#### Acceptance Criteria

12.1. WHEN compliance is checked, THE **ComplianceChecker** SHALL calculate if compliance is mathematically impossible by comparing days_short to workdays_remaining.

12.2. WHEN days_short exceeds workdays_remaining, THE **ComplianceChecker** SHALL set a compliance_risk field to "impossible" in the ComplianceStatus dataclass.

12.3. WHEN the user is not compliant but days_short is less than or equal to workdays_remaining, THE **ComplianceChecker** SHALL set compliance_risk to "possible" in the ComplianceStatus dataclass.

12.4. WHEN the user is compliant, THE **ComplianceChecker** SHALL set compliance_risk to "achieved" in the ComplianceStatus dataclass.

12.5. WHEN days_short equals workdays_remaining (requiring 100% in-office attendance for remaining days), THE **ComplianceChecker** SHALL set compliance_risk to "critical" in the ComplianceStatus dataclass.

12.6. WHEN days_short is greater than 75% of workdays_remaining, THE **ComplianceChecker** SHALL set compliance_risk to "at-risk" in the ComplianceStatus dataclass.

12.7. WHEN displaying status, THE **CLIInterface** SHALL show the compliance_risk status with appropriate messaging: "Compliance: Impossible" for impossible, "Compliance: Critical - Must be in office all remaining days" for critical, "Compliance: At Risk" for at-risk, "Compliance: Possible" for possible, and "Compliance: Achieved" for achieved.

12.8. WHEN compliance_risk is "impossible", THE **CLIInterface** SHALL display a warning message indicating compliance cannot be achieved: "WARNING: Compliance cannot be achieved. Short by [N] days with only [M] workdays remaining."

12.9. WHEN compliance_risk is "critical", THE **CLIInterface** SHALL display a warning message: "CRITICAL: You must be in-office for all [N] remaining workdays to achieve compliance."

12.10. WHEN compliance_risk is "at-risk", THE **CLIInterface** SHALL display a warning message: "AT RISK: You need [N] more in-office days out of [M] remaining workdays ([X]% attendance required)."

12.11. WHEN generating a report, THE **CLIInterface** SHALL include the compliance_risk status and associated warning messages for each reporting period.

---

## Requirements Summary

- **Total Requirements**: 12
- **Total Acceptance Criteria**: 97
- **Components Referenced**: CLIInterface, ConfigurationManager, AttendanceStore, ReportingPeriodCalculator, ComplianceChecker, BusinessDayCalculator

**Requirements documented with 12 requirements and 97 acceptance criteria, each assigned to a specific component. Proceed to detailed design?**
