# DOCX wrong-page repair for blank record-table tails

Use this reference when a screenshot or rendered DOCX shows a blank table fragment before a following section title, such as `专项安全培训教育记录` or `安全生产一级教育情况`.

## Safe scope

The defect is a tail of genuinely empty rows from the immediately preceding training-record table that spills over the page boundary. The repair removes that tail only. It does not reflow the document by changing page setup or typography.

## Current-version gate

Before staging, identify the exact DOCX shown in the screenshot or WPS window. If
the screenshot shows newly entered values, choose at least two visible anchors
(for example, a date and training content) and run the repair with repeated
`--require-text` options. Every anchor must exist in one source DOCX. If not,
stop: the source is an older, copied, or unsaved version, not a pagination defect
that this repair can truthfully solve. Do not create an output or call it fixed.

Example:

```bash
python3 scripts/repair_pagination_blank_tails.py source output \
  --report pagination-repair.json \
  --require-text '2026' \
  --require-text '防灭火专项培训'
```

The JSON report is a version receipt. Keep its source/output roots, matched
relative paths, and SHA-256 values with the change list. Open the matching file
under `output`, never the same relative path under `source`.

## Required checks

1. Obtain explicit user authorization to repair the wrong page and name each affected following heading.
2. Confirm each heading is a direct body paragraph, after at most blank paragraphs, and that the preceding body element is a training-record table with the expected year/month/day/content/hours/result header.
3. Confirm the candidate rows are contiguous table-tail rows with no text, field, drawing, object, bookmark, comment, or reference. Keep the header row even when that table has no populated data rows.
4. Preserve blank paragraphs and any explicit page break between the preceding table and heading. Do not remove rows after the heading, even if they are blank template space.
5. Stage a complete copy, run `scripts/repair_pagination_blank_tails.py`, and write the JSON report outside the staged tree. The script must verify that each changed DOCX differs only in `word/document.xml`.

## Stop conditions

Mark the document `待确认` when the title is inside a table, the predecessor is not a matching training-record table, the heading is absent or ambiguous, the tail contains non-text content, a table has unexpected structure, or the alleged blank rows are not directly before the named heading.

## Verification

Compare source and staged paths. In every changed DOCX, only `word/document.xml` may differ. Reopen the matching **output** DOCX, confirm the named transition has no removable blank tail, and render every changed file; inspect each affected transition page for broken borders, missing headings, or clipping.

When the problem was reported from WPS, native WPS view (or a fresh WPS screenshot
of the output file) is the acceptance evidence. LibreOffice rendering is a useful
structural check but cannot prove WPS pagination. If native WPS verification is
unavailable, report that limitation instead of saying the screenshot defect is
accepted.
