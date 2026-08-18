# Training assessment and platform import

Use this reference only after the router selects `safetyAssessment`.

## Common evidence rules

- Build a question map before drafting: source section, learning objective,
  question type, proposed answer, explanation, and requested score/category.
- Use only supported course content. Do not invent technical limits, correct
  answers, score allocations, difficulty, classifications, trainee details, or
  examination results.
- Keep questions, answer key, scoring rules, and delivery evidence separate. A
  completed paper/import file does not prove that an examination took place.

## Word paper branch

1. Require one DOCX explicitly identified as `assessmentTemplate`. Use it as the
   complete format authority for title, candidate fields, sections, numbering,
   answer spaces, headers/footers, page setup, and answer-key placement.
2. Map each generated question to an existing template location. Preserve runs,
   tables, spacing, and page breaks. If the template lacks safe capacity or a
   needed question type, return `待确认` instead of rebuilding it.
3. Render and inspect the complete paper and answer key. Check numbering,
   answer blanks, total-score arithmetic only when supplied, page breaks, and
   whether answers are exposed in a candidate-facing version.

## Platform-import branch

1. Require the platform's current official XLS/XLSX template, explicitly marked
   `platformTemplate`, and the platform name. Treat exact worksheet names,
   headers, version cells, validation, styles, and answer conventions as fixed.
2. Populate only supported question types and existing template cells. Preserve
   every template worksheet even when a question type has zero questions. Do not
   replace the workbook, add columns, normalize headers, or guess multi-answer
   delimiters.
3. Reopen and validate the workbook against the supplied template, then render
   relevant sheets when available. Hand the file to the user; do not log in,
   upload, schedule an exam, invite candidates, or publish results without
   explicit authorization.

## Question-list branch

Create a structured review list only when no executable Word or import template
was requested. Identify question type, stem, answer, source anchor, and any
`待确认` item. Do not claim platform compatibility for a plain document.
