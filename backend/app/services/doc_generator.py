import asyncio
import json
import logging
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.models.document import Document
from app.models.upload import Upload
from app.models.version import DocumentVersion
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

# Run sections in groups of 3 to avoid overwhelming the AI endpoint while
# still being faster than pure sequential execution.
MAX_PARALLEL_SECTIONS = 3

SECTIONS = [
    ("cover_data", "generate_cover_page"),
    ("business_view", "generate_business_view"),
    ("technical_view", "generate_technical_view"),
    ("source_analysis", "generate_source_analysis"),
    ("database_analysis", "generate_database_analysis"),
    ("api_dependency", "generate_api_dependency"),
    ("process_flow", "generate_process_flow"),
    ("diagrams", "generate_diagrams"),
    ("integration_view", "generate_integration_view"),
    ("security_review", "generate_security_review"),
    ("performance_review", "generate_performance_review"),
    ("reference_data", "generate_reference_tables"),
    ("modification_history", "generate_modification_history"),
    ("ai_recommendations", "generate_ai_recommendations"),
]

COVERAGE_CHECKS = [
    ("tables_used", "database_analysis", "tables"),
    ("function_calls", "api_dependency", "function_modules"),
    ("call_transactions", "api_dependency", "call_transactions"),
]

METADATA_ONLY_KEYS = [
    "conditions", "variables_declared", "windows", "pages",
    "text_elements", "code_blocks", "graphics", "field_references",
]


def validate_coverage(parsed_data: dict, document: Document) -> dict:
    report = {"status": "PASS", "total_extracted": 0, "total_documented": 0, "gaps": []}

    for key in METADATA_ONLY_KEYS:
        count = len(parsed_data.get(key) or [])
        report["total_extracted"] += count
        report["total_documented"] += count

    for src_key, doc_attr, doc_key in COVERAGE_CHECKS:
        extracted = len(parsed_data.get(src_key) or [])
        if not extracted:
            continue

        section = getattr(document, doc_attr, None) or {}
        if isinstance(section, str):
            try:
                section = json.loads(section)
            except ValueError:
                section = {}

        items = section.get(doc_key) if isinstance(section, dict) else None
        documented = len(items) if isinstance(items, list) else 0

        report["total_extracted"] += extracted
        report["total_documented"] += documented
        if documented < extracted:
            report["gaps"].append({
                "object_type": src_key,
                "extracted": extracted,
                "documented": documented,
                "missing": extracted - documented,
            })

    if report["gaps"]:
        report["status"] = "PARTIAL"
    return report


def _enrich_parsed_data_from_graph(parsed_data: dict, graph: dict) -> None:
    """
    Merge repository graph objects into the parsed_data dict so that
    existing AI prompts (which read tables_used, function_calls, classes,
    etc. from parsed_data) automatically receive the full repository context.

    This is additive — existing keys from the regex extractor are preserved
    and graph data is appended without duplication.
    """
    def _merge_list(target_key: str, items: list, name_key: str = "object") -> None:
        existing_names = {
            (i.get("name") or i.get(name_key) or "")
            for i in parsed_data.get(target_key) or []
        }
        for item in items:
            n = item.get(name_key) or item.get("name") or ""
            if n and n not in existing_names:
                parsed_data.setdefault(target_key, []).append({"name": n, **item})
                existing_names.add(n)

    # Tables
    _merge_list("tables_used", [{"name": t.get("object", ""), "operation": "GRAPH"}
                                 for t in graph.get("tables", [])], "name")

    # Function modules
    _merge_list("function_calls", [{"name": f.get("object", "")}
                                    for f in graph.get("functionModules", [])], "name")

    # Classes
    for cls in graph.get("classes", []):
        obj_name = cls.get("object", "")
        if obj_name:
            existing = [c.get("name") for c in parsed_data.get("classes") or []]
            if obj_name not in existing:
                entry = {
                    "name": obj_name,
                    "methods": [m.get("name", "") for m in cls.get("methods", [])],
                    "line_count": 0,
                }
                parsed_data.setdefault("classes", []).append(entry)

    # CDS views
    for cds in graph.get("cdsViews", []):
        obj_name = cds.get("object", "")
        if obj_name:
            existing = [c.get("name") for c in parsed_data.get("cds_views") or []]
            if obj_name not in existing:
                parsed_data.setdefault("cds_views", []).append({"name": obj_name})

    # SmartForms
    for sf in graph.get("smartForms", []):
        obj_name = sf.get("object", "")
        if obj_name:
            existing = [s.get("name") for s in parsed_data.get("smart_forms") or []]
            if obj_name not in existing:
                parsed_data.setdefault("smart_forms", []).append({"name": obj_name})

    # Store the full graph under a dedicated key for AI prompts that want it
    parsed_data["repository_graph"] = graph


async def set_progress(document_id: UUID, status: str, step: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=status, generation_step=step)
        )
        await session.commit()


async def next_version_number(db: AsyncSession, document_id: UUID) -> int:
    result = await db.execute(
        select(func.max(DocumentVersion.version_number))
        .filter(DocumentVersion.document_id == document_id)
    )
    return (result.scalar() or 0) + 1


async def generate_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> Document | None:
    document = (await db.execute(select(Document).filter(Document.id == document_id))).scalars().first()
    if not document:
        logger.error("Document %s not found", document_id)
        return None

    upload = (await db.execute(select(Upload).filter(Upload.id == document.upload_id))).scalars().first()
    if not upload:
        logger.error("Upload %s not found for document %s", document.upload_id, document_id)
        document.status = "failed"
        document.generation_step = "Failed: source upload missing"
        await db.commit()
        return document

    source_code = upload.content or ""
    parsed_data = upload.parsed_metadata or {}

  
    repository_graph: dict = parsed_data.get("repository_graph") or {}
    if repository_graph:
        logger.info(
            "Generating document %s from repository graph for %s (%d chars source, graph types: %s)",
            document_id,
            upload.filename,
            len(source_code),
            ", ".join(
                f"{k}={len(v)}" for k, v in repository_graph.items()
                if isinstance(v, list) and v
            ),
        )
        # Enrich parsed_data with all graph sub-objects so AI prompts
        # that iterate over tables_used, function_calls etc. are complete.
        _enrich_parsed_data_from_graph(parsed_data, repository_graph)
    else:
        logger.info(
            "Generating document %s from %s (%d chars)",
            document_id, upload.filename, len(source_code),
        )

    ai = AIService()
    limiter = asyncio.Semaphore(MAX_PARALLEL_SECTIONS)
    total = len(SECTIONS)
    done = 0

    await set_progress(document_id, "generating", f"Generating sections 0/{total}")

    async def run_section(method_name: str):
        nonlocal done
        async with limiter:
            try:
                return await getattr(ai, method_name)(parsed_data, source_code)
            finally:
                done += 1
                await set_progress(document_id, "generating", f"Generating sections {done}/{total}")

    try:
        results = await asyncio.gather(
            *(run_section(method) for _, method in SECTIONS),
            return_exceptions=True,
        )

        failed = []
        for (attr, _), result in zip(SECTIONS, results):
            if isinstance(result, Exception):
                logger.warning("Section %s failed for %s: %s", attr, document_id, result)
                failed.append(attr)
                setattr(document, attr, {"error": str(result)})
            else:
                setattr(document, attr, result)

        if len(failed) == total:
            document.status = "failed"
            document.generation_step = "Failed: all sections failed"
        else:
            document.status = "completed"
            document.generation_step = "Completed" if not failed else f"Completed with {len(failed)} failed section(s)"
            cover = document.cover_data if isinstance(document.cover_data, dict) else {}
            cover["_coverage_report"] = validate_coverage(parsed_data, document)
            if failed:
                cover["_failed_sections"] = failed
            document.cover_data = cover

        await db.commit()
        logger.info("Document %s finished with status %s (%d failed sections)",
                    document_id, document.status, len(failed))

    except Exception as exc:
        await db.rollback()
        logger.exception("Generation failed for document %s", document_id)
        document.status = "failed"
        document.generation_step = "Failed"
        document.cover_data = {"error": str(exc)}
        await db.commit()
        return document

    if document.status == "completed":
        try:
            version_number = await next_version_number(db, document.id)
            db.add(DocumentVersion(
                document_id=document.id,
                version_number=version_number,
                snapshot={attr: getattr(document, attr) for attr, _ in SECTIONS},
                change_summary="Initial AI generation" if version_number == 1 else "Regenerated from source",
                created_by=user_id,
            ))
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("Could not save version for document %s: %s", document_id, exc)

    return document


async def run_generation(document_id: UUID, user_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await generate_document(db, document_id, user_id)