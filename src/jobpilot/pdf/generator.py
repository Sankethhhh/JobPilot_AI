from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from jobpilot.models import PdfArtifact, TailoredResume, TargetMeta


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")


def generate_pdf(resume: TailoredResume, target: TargetMeta, output_dir: Path) -> PdfArtifact:
    if not resume.full_name or not resume.summary or not resume.experience:
        raise ValueError("Resume missing required sections")

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(target.company)}_{_slug(target.role)}_{target.date}.pdf"
    path = output_dir / filename

    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    left_margin = 42
    right_margin = 42
    content_width = width - left_margin - right_margin
    y = height - 40

    def ensure_space(min_y: int = 72):
        nonlocal y
        if y >= min_y:
            return
        c.showPage()
        y = height - 40
        c.setStrokeColor(colors.HexColor("#d7dbe3"))
        c.line(left_margin, y - 6, width - right_margin, y - 6)
        y -= 18

    def draw_wrapped(
        text: str,
        *,
        font: str = "Helvetica",
        size: int = 10,
        line_height: int = 13,
        max_width: float = content_width,
        indent: float = 0,
        color: str = "#1f2937",
    ) -> None:
        nonlocal y
        ensure_space()
        c.setFont(font, size)
        c.setFillColor(colors.HexColor(color))
        lines = simpleSplit(text, font, size, max_width)
        for line in lines:
            ensure_space()
            c.drawString(left_margin + indent, y, line)
            y -= line_height

    def draw_section_heading(title: str) -> None:
        nonlocal y
        y -= 4
        ensure_space()
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(colors.HexColor("#0f172a"))
        c.drawString(left_margin, y, title.upper())
        c.setStrokeColor(colors.HexColor("#c7ced9"))
        c.line(left_margin + 74, y + 2, width - right_margin, y + 2)
        y -= 14

    # Header
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 19)
    c.drawString(left_margin, y, resume.full_name)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawRightString(width - right_margin, y + 1, f"{target.role} | {target.company}")
    y -= 16
    c.setStrokeColor(colors.HexColor("#0f766e"))
    c.setLineWidth(1.3)
    c.line(left_margin, y, width - right_margin, y)
    y -= 11

    contact_parts = [resume.email, resume.phone, resume.location]
    contact_line = "  |  ".join([item for item in contact_parts if item])
    draw_wrapped(contact_line, font="Helvetica", size=9.5, line_height=12, color="#475569")

    # Summary
    draw_section_heading("Professional Summary")
    draw_wrapped(resume.summary, size=10, line_height=13, color="#111827")

    # Skills
    draw_section_heading("Core Skills")
    skills_text = "  •  ".join(resume.skills)
    draw_wrapped(skills_text, size=9.8, line_height=13, color="#0f172a")

    # Experience
    draw_section_heading("Experience")
    for exp in resume.experience:
        ensure_space(110)
        draw_wrapped(
            f"{exp.title}  |  {exp.company}",
            font="Helvetica-Bold",
            size=10.4,
            line_height=13,
            color="#0f172a",
        )
        if exp.location or exp.period:
            draw_wrapped(
                "  |  ".join([part for part in [exp.location, exp.period] if part]),
                font="Helvetica-Oblique",
                size=9,
                line_height=11,
                color="#64748b",
            )
        for bullet in exp.bullets[:5]:
            draw_wrapped(f"• {bullet}", size=9.5, line_height=12, indent=8, max_width=content_width - 8)
        y -= 4

    if resume.education:
        draw_section_heading("Education")
        for edu in resume.education:
            edu_text = f"{edu.degree}  |  {edu.institution}"
            if edu.year:
                edu_text += f"  |  {edu.year}"
            draw_wrapped(edu_text, size=9.5, line_height=12, color="#0f172a")

    c.save()
    return PdfArtifact(path=path.resolve(), generated_at=datetime.now())
