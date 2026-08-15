#!/usr/bin/env python3
import json
import pathlib
import sys

task = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
errors = []
if task.get("task_type") != "office_personnel_archive":
    errors.append("task_type must be office_personnel_archive")
if task.get("skill_name") != "personnel-archive-assistant":
    errors.append("skill_name mismatch")
if not task.get("source_files"):
    errors.append("source archive or template is required")
payload = task.get("payload") or {}
archive_kind = payload.get("archiveKind") or "personnel"
if archive_kind not in {"personnel", "trainingPeriod"}:
    errors.append("archiveKind must be personnel or trainingPeriod")
if payload.get("mode") not in {"single", "batch"}:
    errors.append("mode must be single or batch")
if archive_kind == "personnel" and payload.get("mode") == "single" and not str(payload.get("personName") or "").strip():
    errors.append("personName is required in single mode")
if archive_kind == "trainingPeriod" and not str(payload.get("department") or "").strip():
    errors.append("department is required for trainingPeriod mode")
source_files = task.get("source_files") or []
zip_sources = [item for item in source_files if pathlib.Path(str(item.get("original_name") or "")).suffix.lower() == ".zip"]
archive_upload = task.get("archive_upload")
if zip_sources and archive_kind != "personnel":
    errors.append("ZIP archive packages are supported only for personnel mode")
if archive_upload and not zip_sources:
    errors.append("archive_upload requires at least one ZIP source")
if zip_sources and len(zip_sources) > 1:
    errors.append("submit one primary employee archive ZIP per task")
print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
raise SystemExit(1 if errors else 0)
