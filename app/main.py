# app/main.py - updated CORS origins
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import performance
from app.routers import disbursed
from app.routers import bank_logging

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# ── CORS ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────
from app.routers import auth, users, contacts, leads, loans, dashboard, conversion, loan_form
from app.routers import bank_dashboard                                          # ← NEW
from app.routers import documents
from app.models import document  # add this import


app.include_router(auth.router,            prefix="/api/auth",           tags=["Auth"])
app.include_router(users.router,           prefix="/api/users",          tags=["Users"])
app.include_router(contacts.router,        prefix="/api/contacts",       tags=["Contacts"])
app.include_router(leads.router,           prefix="/api/leads",          tags=["Leads"])
app.include_router(loans.router,           prefix="/api/loans",          tags=["Loans"])
app.include_router(dashboard.router,       prefix="/api/dashboard",      tags=["Dashboard"])
app.include_router(conversion.router,      prefix="/api/pre-sales",      tags=["Conversion"])
app.include_router(loan_form.router,       prefix="/api/forms",          tags=["Loan Form"])
app.include_router(performance.router, prefix="/api/performance", tags=["Performance"])
app.include_router(disbursed.router, prefix="/api/disbursed", tags=["Disbursed"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(bank_logging.router, prefix="/api/bank-logging", tags=["Bank Logging"])
app.include_router(bank_dashboard.router,  prefix="/api/bank-dashboard", tags=["Bank Dashboard"])  # ← NEW

# ── DB startup ────────────────────────────────────────
from app.database import engine, Base
from app.models import User, Contact, Lead, Loan, LoanFormSubmission   # noqa — needed for table discovery

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()

# ── Health check ──────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
    }

@app.get("/health", tags=["Health"])
async def health():
    return { "status": "ok" }