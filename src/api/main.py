"""FastAPI entry point for the Nifty 100 data API."""
from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .routers import companies, documents, health, peers, portfolio, screener, sectors, valuation


logger = logging.getLogger("nifty100.api")

app = FastAPI(
    title="Nifty 100 Financial Intelligence API",
    description="Read-only API for the Nifty 100 financial data platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log method, path, status, and response duration for each request."""
    started = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


for router_module in (
    companies,
    screener,
    sectors,
    peers,
    valuation,
    portfolio,
    documents,
    health,
):
    app.include_router(router_module.router, prefix="/api/v1")