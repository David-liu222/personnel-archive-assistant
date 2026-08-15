# Existing personnel archives: bulk supplementary training records

Use this reference for a request such as: “Add `2026 | 5 | 25 | 瓦斯基础知识 | 1 | 合格`; the named exceptions are `不合格`.”

## Required inputs

- A source folder that is an extracted copy of the complete one-person-one-file archive, or a ZIP handled through `scripts/archive_package.py`.
- A UTF-8 CSV roster with exact headers `姓名,考核成绩`. Include one row for every intended archive; keep the result explicit for every person.
- The date, training content, hours, and the table label. The default label is `专项安全培训教育记录`.

## Safe procedure

1. Preserve the source folder. For a ZIP, inspect and extract it with `archive_package.py`; never run an unguarded archive extractor.
2. Run `scripts/update_training_records.py` into a fresh staging directory. It only considers a DOCX when the person name appears in its relative path and exactly one table contains both the label and the six expected headers.
3. Review the JSON report. Every requested person must be `updated` or an intentionally accepted `already_present`; investigate `待确认` before continuing.
4. Render changed DOCX files and inspect the table. Check that the record is directly after the appropriate dated record and before any unused blank rows; inspect at least one ordinary result and every exceptional result.
5. Put the change list and JSON report outside the staged archive. For a ZIP, repack the staging tree and verify that no original path is missing.

## Command

```bash
python scripts/update_training_records.py \
  /case/source-tree /case/roster.csv /case/staging-tree \
  --year 2026 --month 5 --day 25 \
  --content "瓦斯基础知识" --hours 1 \
  --report /case/专项培训补录报告.json
```

## Stop conditions

- A roster name matches zero or more than one training-record DOCX.
- A DOCX has zero or more than one matching table, does not have the exact six-column header, or has no populated row whose formatting can be copied.
- The same date/content/hours already exists with a different result.
- The source includes a symbolic link, the output folder already exists, or any requested result is empty.

Do not “repair” a template with no existing record by inventing font, size, alignment, borders, row height, or date-order conventions. Record it as `待确认` and request a reference file instead.
