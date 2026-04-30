"""Domain exceptions for the Color Prediction Game."""


class InsufficientBalanceError(Exception):
    """Raised when a player's wallet balance is insufficient for an operation."""

    def __init__(self, balance, requested):
        self.balance = balance
        self.requested = requested
        super().__init__(
            f"Wallet balance of {balance} is insufficient for amount of {requested}"
        )


class BettingClosedError(Exception):
    """Raised when a bet is placed outside the BETTING phase."""

    def __init__(self, current_phase: str = "unknown"):
        self.current_phase = current_phase
        super().__init__(
            f"Betting is closed. Current phase: {current_phase}"
        )


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_phase: str, target_phase: str):
        self.current_phase = current_phase
        self.target_phase = target_phase
        super().__init__(
            f"Invalid transition from {current_phase} to {target_phase}"
        )


class BetLimitError(Exception):
    """Raised when a bet amount is outside the configured min/max limits."""

    def __init__(self, amount, min_bet, max_bet):
        self.amount = amount
        self.min_bet = min_bet
        self.max_bet = max_bet
        super().__init__(
            f"Bet amount {amount} is outside limits [{min_bet}, {max_bet}]"
        )


class AccountLockedError(Exception):
    """Raised when an action is attempted on a locked account."""

    def __init__(self, locked_until=None):
        self.locked_until = locked_until
        msg = "Account is locked"
        if locked_until:
            msg += f" until {locked_until}"
        super().__init__(msg)


class DepositLimitExceededError(Exception):
    """Raised when a deposit would exceed the configured limit."""

    def __init__(self, limit, current_usage, requested, resets_at=None):
        self.limit = limit
        self.current_usage = current_usage
        self.requested = requested
        self.remaining = limit - current_usage
        self.resets_at = resets_at
        super().__init__(
            f"Deposit of {requested} would exceed limit. "
            f"Remaining allowance: {self.remaining}"
        )


class SelfExcludedError(Exception):
    """Raised when a self-excluded player attempts a restricted action."""

    def __init__(self, ends_at=None):
        self.ends_at = ends_at
        msg = "Account is self-excluded"
        if ends_at:
            msg += f" until {ends_at}"
        super().__init__(msg)


class RateLimitExceededError(Exception):
    """Raised when a player exceeds the API rate limit."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after} seconds"
        )
