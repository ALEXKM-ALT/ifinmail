import csv
import io
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from fpdf import FPDF
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import EmailDelivery, Message, TrackingEvent, User

logger = logging.getLogger("ifinmail.export")

router = APIRouter(prefix="/analytics/export", tags=["export"])


def _delivery_ids_query(days: int, user: User, db: Session):
    since = datetime.now(UTC) - timedelta(days=days)
    return (
        db.query(EmailDelivery.id)
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
    ).subquery()


def _message_ids_query(days: int, user: User, db: Session):
    since = datetime.now(UTC) - timedelta(days=days)
    mailbox_ids = [user.mailbox.id]
    return (
        db.query(Message.id)
        .filter(Message.mailbox_id.in_(mailbox_ids), Message.created_at >= since)
    ).subquery()


@router.get("/csv")
def export_csv(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    output = io.StringIO()
    writer = csv.writer(output)

    since = datetime.now(UTC) - timedelta(days=days)
    mailbox_ids = [user.mailbox.id]

    writer.writerow(["Report: Message Volume"])
    writer.writerow(["Folder", "Count"])
    for row in db.query(Message.folder, sa_func.count(Message.id)).filter(Message.mailbox_id.in_(mailbox_ids)).group_by(Message.folder).all():
        writer.writerow(row)
    writer.writerow([])

    writer.writerow(["Daily Message Volume"])
    writer.writerow(["Date", "Count"])
    for row in db.query(sa_func.date(Message.created_at), sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.created_at >= since
    ).group_by(sa_func.date(Message.created_at)).order_by(sa_func.date(Message.created_at)).all():
        writer.writerow([str(row[0]), row[1]])
    writer.writerow([])

    writer.writerow(["Top Senders"])
    writer.writerow(["Email", "Count"])
    for row in db.query(Message.from_addr, sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.folder == "INBOX", Message.created_at >= since
    ).group_by(Message.from_addr).order_by(sa_func.count(Message.id).desc()).limit(20).all():
        writer.writerow(row)
    writer.writerow([])

    writer.writerow(["Top Recipients"])
    writer.writerow(["Email", "Count"])
    for row in db.query(Message.to_addrs, sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.folder == "SENT", Message.created_at >= since
    ).group_by(Message.to_addrs).order_by(sa_func.count(Message.id).desc()).limit(20).all():
        writer.writerow(row)
    writer.writerow([])

    writer.writerow(["Deliverability"])
    writer.writerow(["Metric", "Value"])
    total = db.query(sa_func.count(EmailDelivery.id)).join(Message).join(User, Message.mailbox_id == User.id).filter(
        User.id == user.id, EmailDelivery.created_at >= since
    ).scalar() or 0
    opened = db.query(sa_func.count(EmailDelivery.id)).filter(
        EmailDelivery.opened_at.isnot(None), EmailDelivery.created_at >= since
    ).join(Message, EmailDelivery.message_id == Message.id).join(User, Message.mailbox_id == User.id).filter(
        User.id == user.id
    ).scalar() or 0
    clicked = db.query(sa_func.count(EmailDelivery.id)).filter(
        EmailDelivery.clicked_at.isnot(None), EmailDelivery.created_at >= since
    ).join(Message, EmailDelivery.message_id == Message.id).join(User, Message.mailbox_id == User.id).filter(
        User.id == user.id
    ).scalar() or 0
    writer.writerow(["Total deliveries", total])
    writer.writerow(["Opened", opened])
    writer.writerow(["Clicked", clicked])
    writer.writerow(["Open rate", f"{round(opened / total * 100, 2) if total else 0}%"])
    writer.writerow(["Click rate", f"{round(clicked / total * 100, 2) if total else 0}%"])
    writer.writerow([])

    delivery_ids = _delivery_ids_query(days, user, db)
    writer.writerow(["Tracking Summary"])
    writer.writerow(["Metric", "Value"])
    total_opens = db.query(sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.event_type == "open"
    ).scalar() or 0
    total_clicks = db.query(sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.event_type == "click"
    ).scalar() or 0
    unique_opens = db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id))).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.event_type == "open"
    ).scalar() or 0
    unique_clicks = db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id))).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.event_type == "click"
    ).scalar() or 0
    writer.writerow(["Total opens", total_opens])
    writer.writerow(["Total clicks", total_clicks])
    writer.writerow(["Unique opens", unique_opens])
    writer.writerow(["Unique clicks", unique_clicks])
    writer.writerow(["Open rate", f"{round(unique_opens / total * 100, 2) if total else 0}%"])
    writer.writerow(["Click rate", f"{round(unique_clicks / total * 100, 2) if total else 0}%"])
    writer.writerow([])

    writer.writerow(["Device Breakdown"])
    writer.writerow(["Device", "Count"])
    for row in db.query(TrackingEvent.device_type, sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.timestamp >= since
    ).group_by(TrackingEvent.device_type).all():
        writer.writerow([row[0] or "unknown", row[1]])
    writer.writerow([])

    writer.writerow(["Location Breakdown"])
    writer.writerow(["City", "Country", "Count"])
    for row in db.query(TrackingEvent.city, TrackingEvent.country, sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)), TrackingEvent.timestamp >= since,
        TrackingEvent.city.isnot(None), TrackingEvent.city != "",
    ).group_by(TrackingEvent.city, TrackingEvent.country).order_by(sa_func.count(TrackingEvent.id).desc()).limit(20).all():
        writer.writerow([row[0], row[1] or "", row[2]])

    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analytics_report_{datetime.now(UTC).strftime('%Y%m%d')}.csv"},
    )


@router.get("/pdf")
def export_pdf(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    mailbox_ids = [user.mailbox.id]

    pdf = FPDF()
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 12, "Analytics Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(0, 8, f"Period: Last {days} days | Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    def section(title):
        pdf.set_font("DejaVu", "B", 13)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(2)

    def kv(label, value):
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 7, f"{label}: {value}", new_x="LMARGIN", new_y="NEXT")

    def table(headers, rows, col_widths=None):
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        if not col_widths:
            col_widths = [pdf.w / len(headers) - 10] * len(headers)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("DejaVu", "", 9)
        for row in rows:
            for i, cell in enumerate(row):
                pdf.cell(col_widths[i], 6, str(cell), border=1)
            pdf.ln()

    total_msgs = db.query(sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids)
    ).scalar() or 0

    section("Message Volume")
    kv("Total messages", total_msgs)
    kv("Period", f"Last {days} days")
    pdf.ln(2)
    folder_data = db.query(Message.folder, sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids)
    ).group_by(Message.folder).all()
    table(["Folder", "Count"], folder_data)

    pdf.ln(4)
    section("Daily Volume")
    daily_data = db.query(sa_func.date(Message.created_at), sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.created_at >= since
    ).group_by(sa_func.date(Message.created_at)).order_by(sa_func.date(Message.created_at)).all()
    table(["Date", "Messages"], [(str(r[0]), r[1]) for r in daily_data])

    pdf.ln(4)
    section("Top Senders")
    sender_data = db.query(Message.from_addr, sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.folder == "INBOX", Message.created_at >= since
    ).group_by(Message.from_addr).order_by(sa_func.count(Message.id).desc()).limit(10).all()
    table(["Email", "Count"], sender_data)

    pdf.ln(4)
    section("Top Recipients")
    recipient_data = db.query(Message.to_addrs, sa_func.count(Message.id)).filter(
        Message.mailbox_id.in_(mailbox_ids), Message.folder == "SENT", Message.created_at >= since
    ).group_by(Message.to_addrs).order_by(sa_func.count(Message.id).desc()).limit(10).all()
    table(["Email", "Count"], recipient_data)

    pdf.add_page()
    section("Deliverability")
    total_del = db.query(sa_func.count(EmailDelivery.id)).join(Message).join(User, Message.mailbox_id == User.id).filter(
        User.id == user.id, EmailDelivery.created_at >= since
    ).scalar() or 0
    opened = db.query(sa_func.count(EmailDelivery.id)).filter(
        EmailDelivery.opened_at.isnot(None), EmailDelivery.created_at >= since
    ).join(Message).join(User, Message.mailbox_id == User.id).filter(User.id == user.id).scalar() or 0
    clicked = db.query(sa_func.count(EmailDelivery.id)).filter(
        EmailDelivery.clicked_at.isnot(None), EmailDelivery.created_at >= since
    ).join(Message).join(User, Message.mailbox_id == User.id).filter(User.id == user.id).scalar() or 0
    kv("Total deliveries", total_del)
    kv("Opened", f"{opened} ({round(opened / total_del * 100, 2) if total_del else 0}%)")
    kv("Clicked", f"{clicked} ({round(clicked / total_del * 100, 2) if total_del else 0}%)")

    pdf.ln(4)
    section("Email Tracking")
    did = _delivery_ids_query(days, user, db)
    total_opens = db.query(sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.event_type == "open"
    ).scalar() or 0
    unique_opens = db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id))).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.event_type == "open"
    ).scalar() or 0
    total_clicks = db.query(sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.event_type == "click"
    ).scalar() or 0
    unique_clicks = db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id))).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.event_type == "click"
    ).scalar() or 0
    kv("Total opens", total_opens)
    kv("Unique opens", unique_opens)
    kv("Total clicks", total_clicks)
    kv("Unique clicks", unique_clicks)

    pdf.ln(4)
    section("Devices")
    device_data = db.query(TrackingEvent.device_type, sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.timestamp >= since
    ).group_by(TrackingEvent.device_type).all()
    table(["Device", "Count"], [(r[0] or "unknown", r[1]) for r in device_data])

    pdf.ln(4)
    section("Locations")
    loc_data = db.query(TrackingEvent.city, TrackingEvent.country, sa_func.count(TrackingEvent.id)).filter(
        TrackingEvent.delivery_id.in_(db.query(did.c.id)), TrackingEvent.timestamp >= since,
        TrackingEvent.city.isnot(None), TrackingEvent.city != "",
    ).group_by(TrackingEvent.city, TrackingEvent.country).order_by(sa_func.count(TrackingEvent.id).desc()).limit(15).all()
    if loc_data:
        table(["City", "Country", "Events"], loc_data)

    pdf_bytes = bytes(pdf.output())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=analytics_report_{datetime.now(UTC).strftime('%Y%m%d')}.pdf"},
    )
