import csv
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import HTTPException
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from logs_ai.web.db import logs

COLUMNS = (
    "id,received_at,source,severity,message,attributes->>'event_kind' AS event_kind,"
    "attributes->>'username' AS username,attributes->>'actor' AS actor"
)


def filters(params):
    now = datetime.now(UTC)
    try:
        start = (
            datetime.fromisoformat(params["from"].replace("Z", "+00:00"))
            if params.get("from")
            else now - timedelta(days=1)
        )
        end = (
            datetime.fromisoformat(params["to"].replace("Z", "+00:00")) if params.get("to") else now
        )
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or end <= start
            or end - start > timedelta(days=93)
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(
            422, "Escolha um intervalo válido, de até 93 dias, com fuso horário."
        ) from None
    clauses, values = ["received_at >= %s", "received_at <= %s"], [start, end]
    for key, column in [("source", "source"), ("kind", "attributes->>'event_kind'")]:
        value = params.get(key, "")
        if len(value) > 160:
            raise HTTPException(422, "Filtro muito longo.")
        if value:
            clauses.append(column + " = %s")
            values.append(value)
    severity = params.get("severity", "")
    if severity:
        if severity not in [str(i) for i in range(8)]:
            raise HTTPException(422, "Severidade inválida.")
        clauses.append("severity = %s")
        values.append(int(severity))
    query = params.get("q", "").strip()
    if len(query) > 160:
        raise HTTPException(422, "Busca limitada a 160 caracteres.")
    if query:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        clauses.append(
            "(message ILIKE %s OR source ILIKE %s OR attributes->>'user"
            "name' ILIKE %s OR attributes->>'actor' ILIKE %s)"
        )
        values += [pattern] * 4
    return " AND ".join(clauses), values


def report(params, page=1, page_size=25, export_limit=None):
    if page < 1 or page > 10000 or page_size not in (10, 25, 50, 100):
        raise HTTPException(422, "Paginação inválida.")
    where, values = filters(params)
    with logs() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        total = conn.execute(
            "SELECT count(*) AS n FROM log_events WHERE " + where, values
        ).fetchone()["n"]
        limit, offset = (export_limit, 0) if export_limit else (page_size, (page - 1) * page_size)
        rows = conn.execute(
            "SELECT "
            + COLUMNS
            + " FROM log_events WHERE "
            + where
            + " ORDER BY received_at DESC,id DESC LIMIT %s OFFSET %s",
            values + [limit, offset],
        ).fetchall()
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "exported": len(rows),
        "truncated": bool(export_limit and total > export_limit),
    }


def csv_cell(value):
    if isinstance(value, datetime):
        value = value.astimezone(UTC).isoformat(timespec="seconds")
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        ["ID", "Recebido em (UTC)", "Origem", "Severidade", "Tipo", "Usuário", "Ator", "Mensagem"]
    )
    for row in rows:
        writer.writerow(
            [
                csv_cell(row.get(k))
                for k in (
                    "id",
                    "received_at",
                    "source",
                    "severity",
                    "event_kind",
                    "username",
                    "actor",
                    "message",
                )
            ]
        )
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def pdf_bytes(result, params):
    if "LogsVera" not in pdfmetrics.getRegisteredFontNames():
        font = Path(rl_config.TTFSearchPath[0]) / "Vera.ttf"
        if not font.exists():
            import reportlab

            font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
        pdfmetrics.registerFont(TTFont("LogsVera", str(font)))
    out = io.BytesIO()
    document = SimpleDocTemplate(
        out,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
    )
    normal = ParagraphStyle("normal", fontName="LogsVera", fontSize=7, leading=10)
    heading = ParagraphStyle(
        "heading",
        fontName="LogsVera",
        fontSize=19,
        leading=25,
        textColor=colors.HexColor("#112539"),
    )
    story = [
        Paragraph("logs-ai · Relatório de eventos", heading),
        Spacer(1, 4 * mm),
        Paragraph(
            escape(
                f"{result['exported']} de {result['total']} eventos · "
                f"Gerado em {datetime.now(UTC):%d/%m/%Y %H:%M UTC}"
            ),
            normal,
        ),
        Paragraph(
            escape("Filtros: " + ", ".join(f"{k}={v}" for k, v in params.items() if v)[:600]),
            normal,
        ),
        Spacer(1, 5 * mm),
    ]
    if result["truncated"]:
        story.append(
            Paragraph(
                "Exportação limitada a 2.000 eventos. Refine os filtros par"
                "a obter o conjunto completo.",
                normal,
            )
        )
    data = [
        [
            Paragraph(text, normal)
            for text in ["Recebido (UTC)", "Origem", "Evento", "Usuário / ator", "Mensagem"]
        ]
    ]
    for row in result["items"]:
        values = [
            row["received_at"].astimezone(UTC).strftime("%d/%m/%Y %H:%M:%S"),
            row["source"],
            row["event_kind"] or "-",
            row["username"] or row["actor"] or "-",
            row["message"][:400],
        ]
        data.append([Paragraph(escape(str(value)), normal) for value in values])
    table = Table(data, colWidths=[34 * mm, 43 * mm, 53 * mm, 42 * mm, 95 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eff5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5eaf0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(table)

    def footer(canvas, doc):
        canvas.setFont("LogsVera", 7)
        canvas.drawString(
            14 * mm, 9 * mm, "logs-ai · Acesso restrito · Dados conforme filtros aplicados"
        )
        canvas.drawRightString(282 * mm, 9 * mm, f"Página {doc.page}")

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
