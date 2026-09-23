from __future__ import annotations

import json
from io import BytesIO
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

REPORT_VERSION = "1"
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN_X = 48
_TOP_Y = _PAGE_HEIGHT - 48
_BOTTOM_Y = 48
_BODY_SIZE = 9
_LINE_HEIGHT = 12


def _format_value(value) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _wrap(text: str, *, font: str, size: float, width: float) -> list[str]:
    words = str(text).replace("\n", " ").split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _rule_lines(result: dict) -> Iterable[tuple[str, bool]]:
    yield (f"{result['provision']} — {result['declaration_type']}", True)
    yield (f"Rule ID: {result['rule_id']}", False)
    yield (f"Preliminary machine result: {result['machine_status']}", False)
    yield (f"Machine value: {_format_value(result['machine_value'])}", False)
    yield (
        "Officer review: "
        f"{result['officer_review']['decision']} "
        f"(revision {result['officer_review']['revision']})",
        False,
    )
    yield (f"Resolved value: {_format_value(result['resolved_value'])}", False)
    if result["officer_review"].get("note"):
        yield (f"Officer note: {result['officer_review']['note']}", False)

    evidence = result.get("evidence") or []
    if not evidence:
        yield ("Evidence references: none recorded", False)
    else:
        for item in evidence:
            yield (
                "Evidence: "
                f"{item['capture_id']} | {item['view_type']} | "
                f"sha256 {item['sha256']}",
                False,
            )


def build_report_pdf(snapshot: dict, *, snapshot_sha256: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(
        buffer,
        pagesize=A4,
        pageCompression=0,
        invariant=1,
    )
    pdf.setTitle("CODEFLUX Inspection Review Report")
    pdf.setAuthor("CODEFLUX")
    pdf.setCreator("CODEFLUX")
    pdf.setSubject("Evidence-backed inspection review record")

    y = _TOP_Y
    content_width = _PAGE_WIDTH - (2 * _MARGIN_X)

    def new_page() -> None:
        nonlocal y
        pdf.showPage()
        y = _TOP_Y

    def line(
        text: str,
        *,
        bold: bool = False,
        size: float = _BODY_SIZE,
        gap_after: float = 0,
    ) -> None:
        nonlocal y
        font = _FONT_BOLD if bold else _FONT
        wrapped = _wrap(text, font=font, size=size, width=content_width)
        required = len(wrapped) * _LINE_HEIGHT + gap_after
        if y - required < _BOTTOM_Y:
            new_page()

        pdf.setFont(font, size)
        for wrapped_line in wrapped:
            pdf.drawString(_MARGIN_X, y, wrapped_line)
            y -= _LINE_HEIGHT
        y -= gap_after

    line("CODEFLUX Inspection Review Report", bold=True, size=16, gap_after=8)
    line(f"Report ID: {snapshot['report_id']}")
    line(f"Report version: {snapshot['report_version']}")
    line(f"Finalization ID: {snapshot['finalization_id']}")
    line(f"Content checksum (snapshot SHA-256): {snapshot_sha256}")
    line(f"Finalized at: {snapshot['finalized_at']}", gap_after=8)

    line("Inspection", bold=True, size=11, gap_after=2)
    inspection = snapshot["inspection"]
    line(f"Inspection ID: {inspection['id']}")
    line(f"Product: {inspection['product_name']}")
    line(
        "Product identifier: "
        f"{inspection.get('product_identifier') or 'Not provided'}",
        gap_after=8,
    )

    line("Officer", bold=True, size=11, gap_after=2)
    officer = snapshot["finalized_by"]
    line(f"Name: {officer['full_name']}")
    line(f"User ID: {officer['user_id']}")
    line(f"Email: {officer['email']}", gap_after=8)

    line("Rule pack", bold=True, size=11, gap_after=2)
    pack = snapshot["rule_pack"]
    line(f"ID: {pack['id']}")
    line(f"Version: {pack['version']}")
    line(f"SHA-256: {pack['sha256']}", gap_after=8)

    line("Reviewed declaration evidence", bold=True, size=11, gap_after=4)
    for result in snapshot["results"]:
        for text, bold in _rule_lines(result):
            line(text, bold=bold)
        line("", gap_after=5)

    line("Important scope note", bold=True, size=11, gap_after=2)
    line(snapshot["disclaimer"])

    pdf.save()
    return buffer.getvalue()
