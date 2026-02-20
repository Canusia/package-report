# Report Module — Product Guide

## What It Does

The Report module lets users generate, schedule, and download data exports from the MyCE platform. Reports run in the background so users don't have to wait — they get an email when the report is ready, or can watch the status update in real-time on the page.

## User Interface

### Reports Tab

The main reports page has two tabs: **Reports** and **My Reports**.

The **Reports** tab is the primary workspace:

1. **Category sidebar** (left) — Click a category (Students, High Schools, Classes, Misc., Instructors) to filter available reports
2. **Report list** (right of sidebar) — Shows reports in the selected category. Click one to load it.
3. **Report form** (bottom left) — Filter options specific to the selected report (e.g. high schools, terms, date ranges)
4. **Description / Recent Runs tabs** (bottom right) — Report description and history of recent runs with status and download links

#### Generating a Report

1. Select a category from the left sidebar
2. Click a report from the list
3. Fill in the filter form (select schools, terms, date ranges, etc.)
4. Click **Generate Export**
5. The report appears in the Recent Runs tab as **PENDING** with a spinner
6. Within a few seconds, the status updates to **RAN** and a **Download Report** link appears
7. An email notification is also sent when the report is ready

### My Reports Tab

The **My Reports** tab shows a consolidated list of every report the user has generated, across all report types. The table includes:

- **Date** — When the report was scheduled
- **Report Name** — Which report was run
- **Status** — PENDING (with spinner), RAN (green badge), or ERROR (red badge)
- **Download** — Link to download completed reports

The table refreshes each time you switch to the tab.

## Status Indicators

| Status | Badge | Meaning |
|--------|-------|---------|
| Pending | Yellow with spinner | Report is queued or processing |
| Ran | Green | Report completed, download available |
| Error | Red | Report failed during execution |

## Role-Based Access

Different user roles see different reports:

| Role | Access | Portal Path |
|------|--------|-------------|
| CE Staff (admin) | All reports, all categories | `/ce/reports/` |
| High School Admin | Reports marked for `highschool_admin`, limited categories (Classes, Students, Misc.) | `/highschool_admin/reports/` |
| Faculty | Reports marked for faculty | `/faculty/reports/` |
| Instructor | Reports marked for instructor | `/instructor/reports/` |

## Superuser Features

Superusers have additional capabilities in the report UI:

- **Edit report title and description** — In the Description tab, click the **Edit** button to modify the report's display title and description. Changes take effect immediately.

## Email Notifications

When a report finishes running, the system sends an email to the user who requested it. The email contains the report title and a link to download the result.

## Background Processing

Reports run asynchronously using a background task worker. This means:

- The page remains responsive while reports generate
- Multiple reports can be queued simultaneously
- Long-running reports don't block the browser
- Status updates appear automatically within a few seconds via smart polling

## Output Formats

Reports typically generate CSV or Excel (XLSX) files. The output is stored securely in S3 private storage and accessed via time-limited presigned URLs.
