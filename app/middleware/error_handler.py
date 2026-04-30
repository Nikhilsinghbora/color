"""FastAPI exception handlers mapping domain exceptions to JSON error responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import (
    AccountLockedError,
    BetLimitError,
    BettingClosedError,
    DepositLimitExceededError,
    InsufficientBalanceError,
    InvalidTransitionError,
    RateLimitExceededError,
    SelfExcludedError,
)


def _error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def insufficient_balance_handler(_request: Request, exc: InsufficientBalanceError) -> JSONResponse:
    return _error_response(
        400,
        "INSUFFICIENT_BALANCE",
        str(exc),
        {"balance": str(exc.balance), "requested": str(exc.requested)},
    )


async def betting_closed_handler(_request: Request, exc: BettingClosedError) -> JSONResponse:
    return _error_response(
        409,
        "BETTING_CLOSED",
        str(exc),
        {"current_phase": exc.current_phase},
    )


async def account_locked_handler(_request: Request, exc: AccountLockedError) -> JSONResponse:
    details: dict = {}
    if exc.locked_until:
        details["locked_until"] = str(exc.locked_until)
    return _error_response(403, "ACCOUNT_LOCKED", str(exc), details or None)


async def deposit_limit_exceeded_handler(_request: Request, exc: DepositLimitExceededError) -> JSONResponse:
    details = {
        "limit": str(exc.limit),
        "current_usage": str(exc.current_usage),
        "requested": str(exc.requested),
        "remaining": str(exc.remaining),
    }
    if exc.resets_at:
        details["resets_at"] = str(exc.resets_at)
    return _error_response(400, "DEPOSIT_LIMIT_EXCEEDED", str(exc), details)


async def self_excluded_handler(_request: Request, exc: SelfExcludedError) -> JSONResponse:
    details: dict = {}
    if exc.ends_at:
        details["ends_at"] = str(exc.ends_at)
    return _error_response(403, "SELF_EXCLUDED", str(exc), details or None)


async def rate_limit_handler(_request: Request, exc: RateLimitExceededError) -> JSONResponse:
    response = _error_response(
        429,
        "RATE_LIMIT_EXCEEDED",
        str(exc),
        {"retry_after": exc.retry_after},
    )
    response.headers["Retry-After"] = str(exc.retry_after)
    return response


async def bet_limit_handler(_request: Request, exc: BetLimitError) -> JSONResponse:
    return _error_response(
        400,
        "BET_LIMIT_VIOLATION",
        str(exc),
        {"amount": str(exc.amount), "min_bet": str(exc.min_bet), "max_bet": str(exc.max_bet)},
    )


async def invalid_transition_handler(_request: Request, exc: InvalidTransitionError) -> JSONResponse:
    return _error_response(
        409,
        "INVALID_TRANSITION",
        str(exc),
        {"current_phase": exc.current_phase, "target_phase": exc.target_phase},
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI app."""
    app.add_exception_handler(InsufficientBalanceError, insufficient_balance_handler)
    app.add_exception_handler(BettingClosedError, betting_closed_handler)
    app.add_exception_handler(AccountLockedError, account_locked_handler)
    app.add_exception_handler(DepositLimitExceededError, deposit_limit_exceeded_handler)
    app.add_exception_handler(SelfExcludedError, self_excluded_handler)
    app.add_exception_handler(RateLimitExceededError, rate_limit_handler)
    app.add_exception_handler(BetLimitError, bet_limit_handler)
    app.add_exception_handler(InvalidTransitionError, invalid_transition_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
