# PolicyWatch – Module 5: Notification and Freshness Tracking

## 1. Introduction

Module 5 manages notifications and tracks the freshness of privacy policy information.

It helps users understand when a website policy was last checked and whether any updates were detected.

## 2. Main Features

- Tracks the last successful check.
- Records failed checks.
- Tracks policy change timestamps.
- Creates notifications when changes are detected.
- Displays unread notifications.
- Allows users to mark notifications as read.
- Identifies source freshness status.

## 3. Freshness Status

| Status | Description |
|---|---|
| Never Checked | No successful check recorded |
| Fresh | Checked within 24 hours |
| Aging | At least 24 hours old |
| Stale | At least 72 hours old |

## 4. Database Tables

### m5_source_freshness
Stores source checking information:
- Source ID
- Last checked time
- Last successful check
- Last change time
- Last error

### m5_notifications
Stores notification information:
- Notification ID
- Source ID
- Title
- Message
- Created time
- Read status

## 5. Project Files

- policywatch_module5/service.py
- policywatch_module5/__init__.py
- demo.py
- tests/test_service.py

## 6. Running the Demo

Run:

python demo.py

## 7. Running Tests

Run:

python -m unittest discover -s tests -v

## 8. Integration Note

This module works with the existing PolicyWatch collector and change-detection components.

It does not independently scrape websites or detect policy changes.

The team should review database and application integration before merging this module.
Live website collection must follow the project's mentor approval requirement.
