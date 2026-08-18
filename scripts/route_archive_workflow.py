#!/usr/bin/env python3
"""Route an archive/training task to exactly one safe workflow branch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


WORKFLOWS = {"archiveUpdate", "mediaLecture", "safetyPresentation", "safetyAssessment"}
MEDIA_SUFFIXES = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".m4a"}
DOCUMENT_SUFFIXES = {".docx", ".pdf", ".md", ".txt", ".pptx"}
PRESENTATION_OUTPUTS = {"ppt", "pptx", "presentation", "slides"}
ASSESSMENT_OUTPUTS = {"wordpaper", "questionlist", "platformimport", "assessment"}
ASSESSMENT_MODES = {"wordPaper", "questionList", "platformImport"}


def as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def source_items(task: dict[str, object]) -> list[dict[str, object]]:
    raw_items = task.get("source_files")
    return [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []


def suffixes(items: list[dict[str, object]]) -> list[str]:
    return [Path(str(item.get("original_name") or "")).suffix.lower() for item in items]


def has_role_with_suffix(items: list[dict[str, object]], role: str, allowed_suffixes: set[str]) -> bool:
    return any(
        str(item.get("role") or "").strip().lower() == role
        and Path(str(item.get("original_name") or "")).suffix.lower() in allowed_suffixes
        for item in items
    )


def has_topic(payload: dict[str, object], *keys: str) -> bool:
    return any(str(payload.get(key) or "").strip() for key in keys)


def needs(branch: str, payload: dict[str, object], items: list[dict[str, object]]) -> list[str]:
    file_suffixes = suffixes(items)
    missing: list[str] = []
    if not items:
        missing.append("至少一个来源文件")
    if branch == "archiveUpdate":
        if payload.get("archiveKind") not in {"personnel", "trainingPeriod"}:
            missing.append("archiveKind: personnel 或 trainingPeriod")
        return missing
    if payload.get("archiveKind") != "trainingPeriod":
        missing.append("archiveKind: trainingPeriod")
    if not str(payload.get("department") or "").strip():
        missing.append("department")
    if branch == "mediaLecture":
        if not has_topic(payload, "lectureTopic"):
            missing.append("lectureTopic")
        if not any(suffix in MEDIA_SUFFIXES for suffix in file_suffixes):
            missing.append("视频或音频来源")
        if ".docx" not in file_suffixes:
            missing.append("DOCX 培训档案模板")
    elif branch == "safetyPresentation":
        if not has_topic(payload, "presentationTopic", "lectureTopic"):
            missing.append("presentationTopic 或 lectureTopic")
        if not any(suffix in DOCUMENT_SUFFIXES | MEDIA_SUFFIXES for suffix in file_suffixes):
            missing.append("讲义、报告或媒体来源")
    elif branch == "safetyAssessment":
        mode = str(payload.get("assessmentMode") or "").strip()
        if not has_topic(payload, "assessmentTopic", "lectureTopic"):
            missing.append("assessmentTopic 或 lectureTopic")
        if mode not in ASSESSMENT_MODES:
            missing.append("assessmentMode: wordPaper、questionList 或 platformImport")
        if not any(suffix in DOCUMENT_SUFFIXES for suffix in file_suffixes):
            missing.append("课程材料")
        if mode == "wordPaper" and not has_role_with_suffix(items, "assessmenttemplate", {".docx"}):
            missing.append("role=assessmentTemplate 的 DOCX 试卷模板")
        if mode == "platformImport":
            if not str(payload.get("assessmentPlatform") or "").strip():
                missing.append("assessmentPlatform")
            if not has_role_with_suffix(items, "platformtemplate", {".xls", ".xlsx"}):
                missing.append("role=platformTemplate 的 XLS/XLSX 官方模板")
    return missing


def choose_branch(task: dict[str, object]) -> tuple[str | None, str]:
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    requested = {item.lower().lstrip(".") for item in as_list(payload.get("requestedOutputs"))}
    explicit = str(payload.get("workflow") or "").strip()
    if explicit:
        return (explicit, "explicit") if explicit in WORKFLOWS else (None, "unknown workflow")
    wants_presentation = bool(requested & PRESENTATION_OUTPUTS)
    wants_assessment = bool(requested & ASSESSMENT_OUTPUTS) or bool(payload.get("assessmentMode"))
    if wants_presentation and wants_assessment:
        return None, "PPT 与考试产物同时请求，需明确顺序或拆分任务"
    if wants_presentation:
        return "safetyPresentation", "requested presentation output"
    if wants_assessment:
        return "safetyAssessment", "requested assessment output"
    if payload.get("lectureSource") == "media":
        return "mediaLecture", "media lecture source"
    return "archiveUpdate", "default archive workflow"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, help="task.json")
    args = parser.parse_args()
    try:
        task = json.loads(args.task.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "待确认", "reason": f"无法读取任务：{error}"}, ensure_ascii=False))
        return 2
    if not isinstance(task, dict):
        print(json.dumps({"status": "待确认", "reason": "任务根节点必须是对象"}, ensure_ascii=False))
        return 2
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    items = source_items(task)
    branch, reason = choose_branch(task)
    if branch is None:
        print(json.dumps({"status": "待确认", "reason": reason, "branch": None}, ensure_ascii=False, indent=2))
        return 2
    missing = needs(branch, payload, items)
    counts: dict[str, int] = {}
    for suffix in suffixes(items):
        counts[suffix or "无扩展名"] = counts.get(suffix or "无扩展名", 0) + 1
    result = {
        "status": "routed" if not missing else "待确认",
        "branch": branch,
        "reason": reason,
        "missing": missing,
        "source_type_counts": counts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.exit(main())
