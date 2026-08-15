#!/usr/bin/env python3
"""Surgically remove safe blank table tails that cause named DOCX headings to spill.

The source archive tree is never modified. The output is a complete copied tree in
which only word/document.xml differs for DOCX files that meet every safety check.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
DEFAULT_HEADINGS = ("专项安全培训教育记录", "安全生产一级教育情况")
DEFAULT_HEADER_TOKENS = ("年", "月", "日", "主要", "内容", "课时", "考核成绩")
UNSAFE_ROW_CONTENT = (
    ".//w:drawing | .//w:object | .//w:pict | .//w:fldChar | .//w:instrText | "
    ".//w:delText | .//w:bookmarkStart | .//w:bookmarkEnd | .//w:commentRangeStart | "
    ".//w:commentRangeEnd | .//w:footnoteReference | .//w:endnoteReference"
)


def local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def normalise(value: str) -> str:
    return "".join(value.replace("\u3000", " ").split())


def visible_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS)).strip()


def is_blank_paragraph(element: etree._Element) -> bool:
    return local_name(element) == "p" and not visible_text(element)


def has_page_break(element: etree._Element) -> bool:
    return bool(
        element.xpath(
            ".//w:br[@w:type='page'] | .//w:lastRenderedPageBreak", namespaces=NS
        )
    )


def is_expected_training_table(table: etree._Element, header_tokens: tuple[str, ...]) -> bool:
    rows = table.xpath("./w:tr", namespaces=NS)
    if not rows:
        return False
    header = normalise(visible_text(rows[0]))
    return all(token in header for token in header_tokens)


def is_semantically_empty_row(row: etree._Element) -> bool:
    return not visible_text(row) and not row.xpath(UNSAFE_ROW_CONTENT, namespaces=NS)


def repair_document_xml(
    xml_bytes: bytes,
    headings: tuple[str, ...],
    header_tokens: tuple[str, ...],
) -> tuple[bytes, list[dict[str, object]]]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    document = etree.fromstring(xml_bytes, parser=parser)
    body = document.find("w:body", namespaces=NS)
    if body is None:
        raise ValueError("word/document.xml has no w:body")

    repairs: list[dict[str, object]] = []
    children = list(body)
    for index, element in enumerate(children):
        if local_name(element) != "p":
            continue
        paragraph_text = normalise(visible_text(element))
        heading = next((value for value in headings if normalise(value) in paragraph_text), None)
        if heading is None:
            continue

        previous_index = index - 1
        blank_paragraphs: list[etree._Element] = []
        while previous_index >= 0 and is_blank_paragraph(children[previous_index]):
            blank_paragraphs.append(children[previous_index])
            previous_index -= 1
        if previous_index < 0 or local_name(children[previous_index]) != "tbl":
            repairs.append({"heading": heading, "status": "待确认_标题前未找到表格"})
            continue

        table = children[previous_index]
        if not is_expected_training_table(table, header_tokens):
            repairs.append({"heading": heading, "status": "待确认_前表不是预期培训记录表"})
            continue

        rows = table.xpath("./w:tr", namespaces=NS)
        blank_tail: list[etree._Element] = []
        for row in reversed(rows):
            if not is_semantically_empty_row(row):
                break
            blank_tail.append(row)
        if not blank_tail:
            repairs.append({"heading": heading, "status": "无需修复"})
            continue

        for row in blank_tail:
            table.remove(row)
        repairs.append(
            {
                "heading": heading,
                "status": "已删除纯空白尾行",
                "removed_rows": len(blank_tail),
                "blank_paragraphs_retained": len(blank_paragraphs),
                "explicit_page_break_retained": any(has_page_break(p) for p in blank_paragraphs),
            }
        )

    if not any(item["status"] == "已删除纯空白尾行" for item in repairs):
        return xml_bytes, repairs
    return etree.tostring(document, encoding="UTF-8", xml_declaration=True), repairs


def replace_document_xml(path: Path, document_xml: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.pagination-", suffix=".docx", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with ZipFile(path, "r") as original, ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as revised:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == "word/document.xml":
                    data = document_xml
                revised.writestr(info, data)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ensure_safe_source_tree(source: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    link = next((path for path in source.rglob("*") if path.is_symlink()), None)
    if link is not None:
        raise ValueError(f"source tree contains a symbolic link: {link.relative_to(source)}")


def report_outside_output(report: Path, output: Path) -> bool:
    try:
        report.relative_to(output)
    except ValueError:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="immutable extracted archive directory")
    parser.add_argument("output", type=Path, help="new staged archive directory")
    parser.add_argument("--report", type=Path, required=True, help="JSON audit report outside output")
    parser.add_argument(
        "--heading",
        action="append",
        dest="headings",
        help="following heading whose predecessor table may be repaired; repeat as needed",
    )
    parser.add_argument(
        "--header-token",
        action="append",
        dest="header_tokens",
        help="required token in the first row of a predecessor training table; repeat to override defaults",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    report = args.report.resolve()
    headings = tuple(args.headings or DEFAULT_HEADINGS)
    header_tokens = tuple(args.header_tokens or DEFAULT_HEADER_TOKENS)
    if not headings or any(not normalise(item) for item in headings):
        raise SystemExit("at least one non-empty heading is required")
    if not header_tokens or any(not normalise(item) for item in header_tokens):
        raise SystemExit("at least one non-empty header token is required")
    ensure_safe_source_tree(source)
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output}")
    if report.exists():
        raise SystemExit(f"refusing to overwrite existing report: {report}")
    if not report_outside_output(report, output):
        raise SystemExit("report must be outside the staged output directory")

    shutil.copytree(source, output, copy_function=shutil.copy2)
    records: list[dict[str, object]] = []
    failures = 0
    for document_path in sorted(output.rglob("*.docx")):
        if document_path.name.startswith("~$"):
            continue
        relative_path = document_path.relative_to(output).as_posix()
        try:
            with ZipFile(document_path, "r") as archive:
                original_xml = archive.read("word/document.xml")
            revised_xml, repairs = repair_document_xml(original_xml, headings, header_tokens)
            changed = revised_xml != original_xml
            if changed:
                replace_document_xml(document_path, revised_xml)
            records.append({"relative_path": relative_path, "changed": changed, "repairs": repairs})
        except Exception as error:
            failures += 1
            records.append({"relative_path": relative_path, "changed": False, "error": str(error)})

    summary = {
        "documents_scanned": len(records),
        "changed_files": sum(1 for record in records if record.get("changed")),
        "repaired_tables": sum(
            1
            for record in records
            for repair in record.get("repairs", [])
            if repair.get("status") == "已删除纯空白尾行"
        ),
        "removed_blank_rows": sum(
            int(repair.get("removed_rows", 0))
            for record in records
            for repair in record.get("repairs", [])
        ),
        "failures": failures,
        "records": records,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in summary if key != "records"}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
