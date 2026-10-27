
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import performance, disbursed, bank_logging
from app.routers import (
    auth,
    users,
    contacts,
    leads,
    loans,
    dashboard,
    conversion,
    loan_form,
    bank_dashboard,
    documents,
)
from app.models import document
from app.database import engine, Base
from app.models import User, Contact, Lead, Loan, LoanFormSubmission


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://corentix-crm.vercel.app",
        "https://crm-fronten.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["Contacts"])
app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
app.include_router(loans.router, prefix="/api/loans", tags=["Loans"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(
    conversion.router, prefix="/api/pre-sales", tags=["Conversion"]
)
app.include_router(
    loan_form.router, prefix="/api/forms", tags=["Loan Form"]
)
app.include_router(
    performance.router, prefix="/api/performance", tags=["Performance"]
)
app.include_router(
    disbursed.router, prefix="/api/disbursed", tags=["Disbursed"]
)
app.include_router(
    documents.router, prefix="/api/documents", tags=["Documents"]
)
app.include_router(
    bank_logging.router, prefix="/api/bank-logging", tags=["Bank Logging"]
)
app.include_router(
    bank_dashboard.router,
    prefix="/api/bank-dashboard",
    tags=["Bank Dashboard"],
)


# Database startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


# Health checks
@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
