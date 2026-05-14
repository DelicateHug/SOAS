"""Multi-section report builder + HTML/PDF export (Phase 10)."""

from __future__ import annotations

import html
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.reporting import Report
from soas_backend.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


# ----- schemas -----


class ReportRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    case_id: UUID | None
    sections: list[dict[str, Any]]
    is_template: bool
    owner_id: UUID

    model_config = {"from_attributes": True}


class ReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    case_id: UUID | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    is_template: bool = False


class ReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sections: list[dict[str, Any]] | None = None
    is_template: bool | None = None


# ----- routes -----


@router.get("", response_model=list[ReportRead])
async def list_reports(
    only_mine: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Report).order_by(Report.updated_at.desc())
    if only_mine:
        q = q.where(Report.owner_id == current_user.id)
    rs = await db.execute(q)
    return list(rs.scalars().all())


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    rs = await db.execute(select(Report).where(Report.id == report_id))
    r = rs.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return r


@router.post("", response_model=ReportRead, status_code=201)
async def create_report(
    body: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = Report(**body.model_dump(), owner_id=current_user.id)
    db.add(r)
    await db.flush()
    return r


@router.patch("/{report_id}", response_model=ReportRead)
async def update_report(
    report_id: UUID,
    body: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(Report).where(Report.id == report_id))
    r = rs.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    await db.flush()
    return r


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(Report).where(Report.id == report_id))
    r = rs.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    await db.delete(r)


def _render_html(report: Report) -> str:
    """Compose a minimal HTML document from the report's sections."""
    parts: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(report.name)}</title>",
        "<style>body{font-family:Inter,sans-serif;max-width:800px;margin:32px auto;padding:0 24px;}"
        "h1{font-size:22px;letter-spacing:-0.02em;}h2{font-size:16px;letter-spacing:-0.015em;margin-top:24px;}"
        "pre{background:#0f1724;color:#e7ecf3;padding:12px;border-radius:6px;overflow:auto;}"
        "table{border-collapse:collapse;width:100%;font-size:12px;}th,td{border:1px solid #e2e6ee;padding:6px;}"
        "</style></head><body>",
        f"<h1>{html.escape(report.name)}</h1>",
    ]
    if report.description:
        parts.append(f"<p>{html.escape(report.description)}</p>")
    for sec in report.sections or []:
        kind = sec.get("kind") or sec.get("type") or "text"
        heading = sec.get("heading")
        if heading:
            parts.append(f"<h2>{html.escape(str(heading))}</h2>")
        if kind == "text":
            parts.append(f"<div>{html.escape(str(sec.get('content', ''))).replace(chr(10), '<br>')}</div>")
        elif kind == "code":
            parts.append(f"<pre><code>{html.escape(str(sec.get('content', '')))}</code></pre>")
        elif kind == "table":
            rows = sec.get("rows") or []
            cols = sec.get("columns") or (list(rows[0].keys()) if rows else [])
            parts.append("<table><thead><tr>")
            parts += [f"<th>{html.escape(str(c))}</th>" for c in cols]
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>")
                parts += [f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in cols]
                parts.append("</tr>")
            parts.append("</tbody></table>")
        else:
            parts.append(f"<div>{html.escape(str(sec.get('content', '')))}</div>")
    parts.append("</body></html>")
    return "".join(parts)


@router.get("/{report_id}/html", response_class=Response)
async def export_html(report_id: UUID, db: AsyncSession = Depends(get_db)):
    rs = await db.execute(select(Report).where(Report.id == report_id))
    r = rs.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    body = _render_html(r)
    return Response(content=body, media_type="text/html")


@router.get("/{report_id}/pdf", response_class=Response)
async def export_pdf(report_id: UUID, db: AsyncSession = Depends(get_db)):
    """Render to PDF via WeasyPrint. Returns 503 if WeasyPrint isn't installed."""
    rs = await db.execute(select(Report).where(Report.id == report_id))
    r = rs.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError:
        raise HTTPException(status_code=503, detail="WeasyPrint not installed on backend")
    body = _render_html(r)
    pdf_bytes = HTML(string=body).write_pdf()
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=\"{r.name}.pdf\"",
    })
