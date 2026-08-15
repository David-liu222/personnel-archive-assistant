# Format-frozen archive updates

Use this reference whenever the request says to change information but not formatting. The source file is the complete visual authority.

## Supported scope

- Existing text, form fields, and table cells in DOCX.
- Existing cells in XLSX.
- A new DOCX table record only when the user requests it and a populated adjacent record can be cloned exactly.

Do not convert or edit PDF, legacy `.doc`, images, shortcuts, macros, or unsupported formats in place. Preserve them and report `待确认`.

## Before changing a value

1. Identify the exact file, target, original value, replacement value, and a stable local anchor such as field label, table title, row/column header, or nearby text.
2. Confirm the target is unique. A duplicate name, date, or field label without a unique local anchor is unsafe.
3. Capture the relevant formatting baseline. For DOCX: target cell `w:tcPr`, paragraph `w:pPr`, run `w:rPr`, table geometry, and surrounding row. For XLSX: cell style, number format, merge state, row/column dimension, print setup, and sheet name.

## DOCX editing rules

- Modify the existing run or underlying `w:t` node; never use `paragraph.text` or `cell.text` to replace content.
- Keep run segmentation and `w:rPr` intact. If a value crosses several runs, replace it without merging runs or rebuild the paragraph; otherwise leave it unchanged and request a more specific target.
- Retain paragraph, cell, row, table, section, header/footer, relationship, and image XML. Do not rebuild a table to change one value.
- For a requested new table record, clone the complete `w:tr` of a neighboring populated record and replace only the intended values. Insert before preallocated blank rows and preserve date order. Never use `table.add_row()`.

## XLSX editing rules

- Assign only the intended existing cell value; preserve its style, formula state, merge membership, data validation, conditional formatting, number format, hyperlinks, comments, row height, and column width.
- Keep all sheet names, workbook names, tables, charts, print areas, page breaks, freeze panes, hidden states, and formula definitions unchanged.
- Do not use dataframe export or recreate a worksheet. If an update needs an inserted row/column or changes an existing formula, stop for confirmation and a reference layout.

## Verification gate

1. Reopen every changed file and confirm only the intended values changed.
2. Compare each DOCX target's cell/paragraph/run formatting with its baseline or cloned reference; compare XLSX target style and all affected sheet layout settings with their baseline.
3. Render changed DOCX/XLSX files. Inspect for missing text, clipping, overflow, altered table geometry, unexpected wraps, row-height changes, broken page breaks, or missing objects.
4. If the new content causes a visual change that cannot be avoided without altering formatting, mark that file `待确认`; do not make compensating layout changes.
5. Record the exact file, field, old value, new value, reference anchor, and verification result in the change list.
