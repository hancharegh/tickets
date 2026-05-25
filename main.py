"""
Theater Booking System — FastAPI Backend
"""

import io
import uuid
import base64
import qrcode
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# ─── Database ─────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./theater.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    **({} if DATABASE_URL.startswith("postgresql") else {"connect_args": {"check_same_thread": False}})
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Ticket(Base):
    __tablename__ = "tickets"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seat_id     = Column(String, unique=True, index=True, nullable=False)
    row_num     = Column(Integer, nullable=False)
    seat_num    = Column(Integer, nullable=False)
    section     = Column(String, default="Партер")
    guest_name  = Column(String, nullable=False)
    email       = Column(String, nullable=True)
    used        = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    used_at     = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Theater Booking", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def generate_qr_base64(data: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ─── Schemas ──────────────────────────────────────────────────────────────────

class BookingRequest(BaseModel):
    seat_id:    str
    row_num:    int
    seat_num:   int
    section:    str = "Партер"
    guest_name: str
    email:      str = ""


class ScanRequest(BaseModel):
    ticket_id: str


class QRRestoreRequest(BaseModel):
    email: str

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/scan", response_class=HTMLResponse)
async def scan_page():
    with open("templates/scan.html", encoding="utf-8") as f:
        return f.read()


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    with open("templates/admin.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/seats")
async def get_seats():
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).all()
        return {
            "booked": [
                {
                    "seat_id":    t.seat_id,
                    "used":       t.used,
                    "guest_name": t.guest_name,
                    "email":      t.email or "",
                }
                for t in tickets
            ]
        }
    finally:
        db.close()


@app.post("/api/book")
async def book_seat(req: BookingRequest):
    db = SessionLocal()
    try:
        existing = db.query(Ticket).filter(Ticket.seat_id == req.seat_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Место уже занято")

        ticket = Ticket(
            id         = str(uuid.uuid4()),
            seat_id    = req.seat_id,
            row_num    = req.row_num,
            seat_num   = req.seat_num,
            section    = req.section,
            guest_name = req.guest_name.strip(),
            email      = req.email.strip().lower() if req.email else None,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        qr_b64 = generate_qr_base64(ticket.id)

        return {
            "ticket_id":  ticket.id,
            "seat_id":    ticket.seat_id,
            "row_num":    ticket.row_num,
            "seat_num":   ticket.seat_num,
            "section":    ticket.section,
            "guest_name": ticket.guest_name,
            "email":      ticket.email or "",
            "created_at": ticket.created_at.isoformat(),
            "qr_base64":  qr_b64,
        }
    finally:
        db.close()


@app.post("/api/scan")
async def scan_ticket(req: ScanRequest):
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == req.ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Билет не найден")
        if ticket.used:
            raise HTTPException(
                status_code=410,
                detail=f"Билет уже использован в {ticket.used_at.strftime('%H:%M %d.%m.%Y')}"
            )
        ticket.used    = True
        ticket.used_at = datetime.utcnow()
        db.commit()
        return {
            "ok":         True,
            "guest_name": ticket.guest_name,
            "section":    ticket.section,
            "row_num":    ticket.row_num,
            "seat_num":   ticket.seat_num,
        }
    finally:
        db.close()


@app.post("/api/restore-qr")
async def restore_qr(req: QRRestoreRequest):
    """Find all active tickets by email and return their QR codes."""
    db = SessionLocal()
    try:
        email = req.email.strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email не указан")

        tickets = db.query(Ticket).filter(
            Ticket.email == email,
            Ticket.used == False
        ).all()

        if not tickets:
            raise HTTPException(
                status_code=404,
                detail="Активных билетов с этим email не найдено"
            )

        result = []
        for t in tickets:
            result.append({
                "ticket_id":  t.id,
                "guest_name": t.guest_name,
                "section":    t.section,
                "row_num":    t.row_num,
                "seat_num":   t.seat_num,
                "created_at": t.created_at.isoformat(),
                "qr_base64":  generate_qr_base64(t.id),
            })
        return {"tickets": result}
    finally:
        db.close()


@app.delete("/api/cancel/{ticket_id}")
async def cancel_ticket(ticket_id: str):
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Билет не найден")
        if ticket.used:
            raise HTTPException(status_code=410, detail="Билет уже был использован — возврат невозможен")
        db.delete(ticket)
        db.commit()
        return {"ok": True, "message": "Билет успешно возвращён"}
    finally:
        db.close()


@app.get("/api/admin/tickets")
async def admin_list():
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
        return [
            {
                "ticket_id":  t.id,
                "seat_id":    t.seat_id,
                "section":    t.section,
                "row_num":    t.row_num,
                "seat_num":   t.seat_num,
                "guest_name": t.guest_name,
                "email":      t.email or "",
                "used":       t.used,
                "created_at": t.created_at.isoformat(),
                "used_at":    t.used_at.isoformat() if t.used_at else None,
            }
            for t in tickets
        ]
    finally:
        db.close()


@app.get("/api/ticket-qr/{ticket_id}")
async def get_ticket_qr(ticket_id: str):
    """Return QR code for a ticket by ID (admin use)."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Билет не найден")
        return {"qr_base64": generate_qr_base64(ticket.id)}
    finally:
        db.close()
