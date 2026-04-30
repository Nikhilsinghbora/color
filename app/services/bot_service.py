"""Bot service for simulating player activity.

Bots place bets in active rounds to create activity, but their data is not
persisted to the database. They appear in winner lists if they win.

Requirements: User-requested feature for consistent round activity.
"""

import logging
import random
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class BotBet(NamedTuple):
    """In-memory representation of a bot bet."""

    bot_id: UUID
    bot_name: str
    round_id: UUID
    color: str
    amount: Decimal
    odds_at_placement: Decimal


class BotPayout(NamedTuple):
    """In-memory representation of a bot payout."""

    bot_id: UUID
    bot_name: str
    amount: Decimal


# Bot name pool
BOT_NAMES = [
    "LuckyPlayer",
    "GameMaster",
    "WinStreak",
    "BigWinner",
    "ProGamer",
    "FortuneKing",
    "SpinMaster",
    "JackpotHunter",
    "RiskTaker",
    "SmartBetter",
    "CasinoKing",
    "WealthyOne",
    "GoldRush",
    "DiamondHands",
    "MoneyMaker",
    "VictorySeeker",
    "ChampionBet",
    "ElitePlayer",
    "MegaWin",
    "PowerBetter",
]

# All possible bet colors including numbers and big/small
BET_CHOICES = [
    "green",
    "red",
    "violet",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "big",
    "small",
]

# Bet amounts bots can place (in dollars)
BET_AMOUNTS = [
    Decimal("10"),
    Decimal("20"),
    Decimal("50"),
    Decimal("100"),
    Decimal("200"),
    Decimal("500"),
]


class BotService:
    """Service for managing bot bets in game rounds."""

    def __init__(self):
        # In-memory storage: round_id -> list of BotBet
        self._bets_by_round: dict[UUID, list[BotBet]] = {}

    def generate_bots_for_round(self, round_id: UUID, odds_map: dict[str, Decimal]) -> list[BotBet]:
        """Generate random bot bets for a round.

        Args:
            round_id: The round ID
            odds_map: Map of color -> odds (e.g., {"green": Decimal("2.0")})

        Returns:
            List of bot bets placed in this round
        """
        # Random number of bots (3-8 per round)
        num_bots = random.randint(3, 8)

        bots = []
        used_names = set()

        for _ in range(num_bots):
            # Pick unique bot name for this round
            available_names = [n for n in BOT_NAMES if n not in used_names]
            if not available_names:
                break  # All names used

            bot_name = random.choice(available_names)
            used_names.add(bot_name)

            # Generate bet details
            bot_id = uuid4()
            color = random.choice(BET_CHOICES)
            amount = random.choice(BET_AMOUNTS)

            # Get odds for this color
            odds = odds_map.get(color, Decimal("2.0"))

            bet = BotBet(
                bot_id=bot_id,
                bot_name=bot_name,
                round_id=round_id,
                color=color,
                amount=amount,
                odds_at_placement=odds,
            )
            bots.append(bet)

        # Store in memory
        self._bets_by_round[round_id] = bots

        logger.info(f"Generated {len(bots)} bot bets for round {round_id}")
        return bots

    def get_bots_for_round(self, round_id: UUID) -> list[BotBet]:
        """Get all bot bets for a specific round."""
        return self._bets_by_round.get(round_id, [])

    def calculate_bot_payouts(
        self, round_id: UUID, winning_number: int, winning_color: str
    ) -> list[BotPayout]:
        """Calculate payouts for winning bots in a round.

        Args:
            round_id: The round ID
            winning_number: The winning number (0-9)
            winning_color: The winning color

        Returns:
            List of bot payouts for winners
        """
        bots = self.get_bots_for_round(round_id)
        if not bots:
            return []

        payouts = []
        service_fee = Decimal("0.98")  # 2% service fee

        for bot in bots:
            is_winner = False

            # Check if bot won based on bet type
            if bot.color == winning_color:
                is_winner = True
            elif bot.color == str(winning_number):
                is_winner = True
            elif bot.color == "big" and winning_number >= 5:
                is_winner = True
            elif bot.color == "small" and winning_number < 5:
                is_winner = True

            if is_winner:
                # Calculate payout with 2% service fee deducted
                payout_amount = (bot.amount * bot.odds_at_placement * service_fee).quantize(
                    Decimal("0.01")
                )

                payout = BotPayout(
                    bot_id=bot.bot_id,
                    bot_name=bot.bot_name,
                    amount=payout_amount,
                )
                payouts.append(payout)

        logger.info(f"Calculated {len(payouts)} bot payouts for round {round_id}")
        return payouts

    def get_bot_stats_for_round(self, round_id: UUID) -> dict:
        """Get statistics about bot activity in a round.

        Returns:
            Dict with total_bots, total_bet_amount
        """
        bots = self.get_bots_for_round(round_id)
        total_amount = sum(bot.amount for bot in bots)

        return {
            "total_bots": len(bots),
            "total_bet_amount": total_amount,
        }

    def clear_round_bots(self, round_id: UUID) -> None:
        """Clear bot data for a completed round to free memory."""
        if round_id in self._bets_by_round:
            del self._bets_by_round[round_id]
            logger.debug(f"Cleared bot data for round {round_id}")


# Singleton instance
bot_service = BotService()
