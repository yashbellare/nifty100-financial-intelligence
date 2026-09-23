"""Valuation routes reserved for the Day 40 API implementation."""
from fastapi import APIRouter


router = APIRouter(prefix="/market-cap", tags=["valuation"])