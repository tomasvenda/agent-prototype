import uuid
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import run_agent_turn
from database import (
    init_db, is_valid_date, count_appointments, MAX_PER_DAY,
    list_appointments, get_appointment, create_appointment, delete_appointment,
)
from fastapi.responses import FileResponse

init_db()

app = FastAPI(
    title="Dealership After-Sales Assistant",
    description="An agentic assistant for booking and cancelling workshop appointments."
)

conversations: dict[str, list] = {}


# ======================================================================
# CHAT (from Step 2, unchanged)
# ======================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str

@app.get("/", include_in_schema=False)
def home():
    """Serves the chat page when someone opens the site in a browser."""
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    messages = conversations.setdefault(session_id, [])

    history_length = len(messages)
    messages.append({"role": "user", "content": req.message})

    try:
        reply = run_agent_turn(messages)
    except Exception as e:
        del messages[history_length:]
        raise HTTPException(status_code=502, detail=f"Agent error: {e}")

    return ChatResponse(reply=reply, session_id=session_id)


@app.delete("/chat/{session_id}", status_code=204)
def reset_chat(session_id: str):
    if session_id not in conversations:
        raise HTTPException(status_code=404, detail="Session not found")
    del conversations[session_id]


# ======================================================================
# APPOINTMENTS (new in Step 3)
# ======================================================================

ServiceType = Literal[
    "Oil Change", "Tire Rotation", "Brake Inspection", "Full Service / MOT", "General Diagnostics"
]

class AppointmentIn(BaseModel):
    """What the client sends to create a booking."""
    customer_name: str
    service_type: ServiceType
    date: str

class Appointment(AppointmentIn):
    """What the server sends back: the same fields, plus the id."""
    id: int

class Availability(BaseModel):
    date: str
    available: bool
    booked: int
    capacity: int


@app.get("/availability/{date}", response_model=Availability)
def availability(date: str):
    if not is_valid_date(date):
        raise HTTPException(status_code=400, detail="Date must be a real date in YYYY-MM-DD format.")
    booked = count_appointments(date)
    return Availability(date=date, available=booked < MAX_PER_DAY, booked=booked, capacity=MAX_PER_DAY)


@app.get("/appointments", response_model=list[Appointment])
def get_appointments(date: str | None = None):
    if date is not None and not is_valid_date(date):
        raise HTTPException(status_code=400, detail="Date must be a real date in YYYY-MM-DD format.")
    return list_appointments(date)


@app.get("/appointments/{appointment_id}", response_model=Appointment)
def read_appointment(appointment_id: int):
    appt = get_appointment(appointment_id)
    if appt is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return appt


@app.post("/appointments", response_model=Appointment, status_code=201)
def book(appt: AppointmentIn):
    if not is_valid_date(appt.date):
        raise HTTPException(status_code=400, detail="Date must be a real date in YYYY-MM-DD format.")
    if count_appointments(appt.date) >= MAX_PER_DAY:
        raise HTTPException(status_code=409, detail=f"{appt.date} is fully booked.")
    new_id = create_appointment(appt.customer_name, appt.service_type, appt.date)
    return Appointment(id=new_id, **appt.model_dump())


@app.delete("/appointments/{appointment_id}", status_code=204)
def cancel(appointment_id: int):
    if not delete_appointment(appointment_id):
        raise HTTPException(status_code=404, detail="Appointment not found.")