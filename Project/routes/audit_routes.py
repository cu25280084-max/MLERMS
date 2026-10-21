
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session,
    request,
    Response
)

import csv
import io

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from models.audit_model import (
    get_audit_logs,
    get_audit_summary
)

from models.asset_model import get_all_units


audit_bp = Blueprint(
    "audit",
    __name__,
    url_prefix="/audit"
)


@audit_bp.route("/")
def audit_home():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Keep the same unit context as the dashboard and other unit pages.
    units = get_all_units()
    requested_unit_id = request.args.get("unit_id", "").strip()
    selected_unit_id = requested_unit_id or session.get("selected_unit_id")
    selected_unit = next(
        (unit for unit in units if str(unit.get("unit_id")) == str(selected_unit_id)),
        None
    )

    if requested_unit_id and selected_unit is None:
        return "Unit not found.", 404

    # Match the dashboard's default behaviour when no unit has been selected yet.
    if selected_unit is None and units:
        selected_unit = units[0]
        session["selected_unit_id"] = selected_unit["unit_id"]
    elif selected_unit is not None:
        session["selected_unit_id"] = selected_unit["unit_id"]

    module = request.args.get("module", "").strip()
    action = request.args.get("action", "").strip()
    user_id = request.args.get("user_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    audit_logs = get_audit_logs(
        module=module or None,
        action=action or None,
        user_id=user_id or None,
        date_from=date_from or None,
        date_to=date_to or None
    )

    audit_summary = get_audit_summary()

    return render_template(
        "audit/index.html",
        units=units,
        selected_unit=selected_unit,
        audit_logs=audit_logs,
        audit_summary=audit_summary,
        selected_module=module,
        selected_action=action,
        selected_user_id=user_id,
        date_from=date_from,
        date_to=date_to
    )


@audit_bp.route("/export/csv")
def export_csv():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    module = request.args.get("module", "").strip()
    action = request.args.get("action", "").strip()
    user_id = request.args.get("user_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    audit_logs = get_audit_logs(
        limit=10000,
        module=module or None,
        action=action or None,
        user_id=user_id or None,
        date_from=date_from or None,
        date_to=date_to or None
    )

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Audit ID",
        "Date & Time",
        "User ID",
        "Username",
        "Action",
        "Module",
        "Record ID",
        "Description"
    ])

    for log in audit_logs:

        writer.writerow([
            log.get("audit_id"),
            log.get("created_at"),
            log.get("user_id"),
            log.get("username") or "System / Unknown",
            log.get("action"),
            log.get("module"),
            log.get("record_id") or "-",
            log.get("description")
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=mlerms_audit_report.csv"
    )

    return response

@audit_bp.route("/export/pdf")
def export_pdf():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    module = request.args.get("module", "").strip()
    action = request.args.get("action", "").strip()
    user_id = request.args.get("user_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    audit_logs = get_audit_logs(
        limit=10000,
        module=module or None,
        action=action or None,
        user_id=user_id or None,
        date_from=date_from or None,
        date_to=date_to or None
    )

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=12
    )

    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=9
    )

    elements = []

    # Title
    elements.append(
        Paragraph(
            "MLERMS - Audit & Reporting",
            title_style
        )
    )

    elements.append(
        Paragraph(
            "Military Logistics & Equipment Readiness Management System",
            subtitle_style
        )
    )

    # Report information
    generated_at = datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    elements.append(
        Paragraph(
            f"<b>Generated:</b> {generated_at}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<b>Total Records:</b> {len(audit_logs)}",
            styles["Normal"]
        )
    )

    # Applied filters
    filter_parts = []

    if module:
        filter_parts.append(f"Module: {module}")

    if action:
        filter_parts.append(f"Action: {action}")

    if user_id:
        filter_parts.append(f"User ID: {user_id}")

    if date_from:
        filter_parts.append(f"From: {date_from}")

    if date_to:
        filter_parts.append(f"To: {date_to}")

    if filter_parts:
        filter_text = " | ".join(filter_parts)
    else:
        filter_text = "No filters applied"

    elements.append(
        Paragraph(
            f"<b>Filters:</b> {filter_text}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 10))


    # Table header
    table_data = [
        [
            "ID",
            "Date & Time",
            "User",
            "Action",
            "Module",
            "Record ID",
            "Description"
        ]
    ]


    # Table rows
    for log in audit_logs:

        username = log.get("username") or "System / Unknown"
        record_id = log.get("record_id") or "-"

        table_data.append([
            str(log.get("audit_id", "")),
            str(log.get("created_at", "")),
            Paragraph(username, cell_style),
            Paragraph(str(log.get("action", "")), cell_style),
            Paragraph(str(log.get("module", "")), cell_style),
            Paragraph(str(record_id), cell_style),
            Paragraph(
                str(log.get("description", "")),
                cell_style
            )
        ])


    # Create table
    table = Table(
        table_data,
        colWidths=[
            12 * mm,
            35 * mm,
            28 * mm,
            28 * mm,
            28 * mm,
            28 * mm,
            105 * mm
        ],
        repeatRows=1
    )


    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#1f2937")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, 0),
                7
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, 0),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.grey
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f8fafc")
                ]
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ])
    )


    elements.append(table)

    document.build(elements)

    buffer.seek(0)

    response = Response(
        buffer.getvalue(),
        mimetype="application/pdf"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=mlerms_audit_report.pdf"
    )

    return response