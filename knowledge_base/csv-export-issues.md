---
id: csv-export-issues
title: CSV export problems
category: product
---

# CSV export problems

## Missing columns

Exports include the columns currently shown in the list view. If a column is missing, enable it with **View > Columns** and export again. Custom fields appear after the built-in ones.

## Garbled characters

The file is UTF-8 with a byte order mark. In Excel use **Data > From Text/CSV** and choose UTF-8, or open the file in Google Sheets.

## Large exports time out

Exports above 50,000 rows run in the background. You get an email with a download link that works for 24 hours. If a background export fails, split it by project or date range and try again.

## Dates are wrong

Dates are exported in the time zone set in **Profile > Preferences**. Check that setting if dates seem shifted by several hours.

For a full copy of everything in your workspace use the workspace export, described in [Export your workspace data](export-workspace-data.md).
