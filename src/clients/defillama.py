"""
Local DefiLlama data loader - works with local JSON file.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class DefiLlamaLoader:
    """Load crypto raises from local DefiLlama JSON file."""

    def __init__(self, data_file: str | None = None):
        """
        Initialize loader.

        Args:
            data_file: Path to JSON file. Defaults to data/defillama-raises.json
        """
        if data_file is None:
            # Default to project data directory
            project_root = Path(__file__).parent.parent.parent
            data_file = project_root / "data" / "defillama-raises.json"

        self.data_file = Path(data_file)

        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

    def load_raises(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Load raises from JSON file.

        Args:
            limit: Optional limit on number of raises to return

        Returns:
            List of raise dictionaries
        """
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)

            raises = data.get("raises", [])

            if limit:
                raises = raises[:limit]

            logger.info(f"Loaded {len(raises)} raises from {self.data_file.name}")
            return raises

        except Exception as e:
            logger.error(f"Error loading raises: {e}")
            return []

    def filter_by_date(
        self, raises: list[dict[str, Any]], since_days: int
    ) -> list[dict[str, Any]]:
        """
        Filter raises by date.

        Args:
            raises: List of raise dicts
            since_days: Only return raises from last N days

        Returns:
            Filtered list
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=since_days)
        cutoff_timestamp = int(cutoff_date.timestamp())

        filtered = [r for r in raises if r.get("date", 0) >= cutoff_timestamp]

        logger.info(
            f"Filtered to {len(filtered)} raises from last {since_days} days"
        )
        return filtered

    def parse_raise(self, raise_data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse DefiLlama raise into normalized format for database.

        Args:
            raise_data: Raw raise dict from JSON

        Returns:
            Normalized dict with keys:
                - project_name: str
                - round: str
                - amount_usd: float (in millions)
                - announced_on: datetime
                - investors: list[str]
                - source_url: str
                - category: str
                - chains: list[str]
                - raw_data: dict (original data for reference)
        """
        # Parse date
        announced_on = None
        if "date" in raise_data and raise_data["date"]:
            try:
                announced_on = datetime.fromtimestamp(raise_data["date"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid date: {raise_data.get('date')}")

        # Combine lead and other investors
        investors = []
        if "leadInvestors" in raise_data and raise_data["leadInvestors"]:
            investors.extend(raise_data["leadInvestors"])
        if "otherInvestors" in raise_data and raise_data["otherInvestors"]:
            investors.extend(raise_data["otherInvestors"])

        return {
            "project_name": raise_data.get("name", "Unknown"),
            "round": raise_data.get("round", "Unknown"),
            "amount_usd": float(raise_data.get("amount", 0)),
            "announced_on": announced_on,
            "investors": investors,
            "source_url": raise_data.get("source", ""),
            "category": raise_data.get("category", ""),
            "category_group": raise_data.get("categoryGroup", ""),
            "sector": raise_data.get("sector", ""),
            "chains": raise_data.get("chains", []),
            "valuation": raise_data.get("valuation"),
            "raw_data": raise_data,  # Keep original for reference
        }

    def get_summary(self, raises: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Get summary statistics from raises.

        Returns:
            Dict with counts, amounts, top investors, etc.
        """
        total_raises = len(raises)
        total_amount = sum(r.get("amount") or 0 for r in raises)

        # Count by round
        rounds = {}
        for r in raises:
            round_type = r.get("round", "Unknown")
            rounds[round_type] = rounds.get(round_type, 0) + 1

        # Count by category
        categories = {}
        for r in raises:
            cat = r.get("category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1

        # Top investors (by number of deals)
        investor_counts = {}
        for r in raises:
            for inv in r.get("leadInvestors", []) + r.get("otherInvestors", []):
                investor_counts[inv] = investor_counts.get(inv, 0) + 1

        top_investors = sorted(
            investor_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "total_raises": total_raises,
            "total_amount_usd": total_amount,
            "rounds": rounds,
            "categories": categories,
            "top_investors": dict(top_investors),
        }


# Example usage
if __name__ == "__main__":
    loader = DefiLlamaLoader()

    # Load all raises
    raises = loader.load_raises()
    print(f"\n📊 Total raises: {len(raises)}")

    # Filter to last 90 days
    recent_raises = loader.filter_by_date(raises, since_days=90)
    print(f"📅 Recent raises (90 days): {len(recent_raises)}")

    # Show summary
    summary = loader.get_summary(recent_raises)
    print(f"\n💰 Total amount: ${summary['total_amount_usd']:.1f}M")
    print(f"\n🏆 Top 5 investors:")
    for investor, count in list(summary["top_investors"].items())[:5]:
        print(f"  {investor}: {count} deals")

    # Parse and show first 3 raises
    print(f"\n📋 Sample raises:")
    for raise_data in recent_raises[:3]:
        parsed = loader.parse_raise(raise_data)
        print(
            f"\n  • {parsed['project_name']}: ${parsed['amount_usd']:.1f}M ({parsed['round']})"
        )
        print(f"    Date: {parsed['announced_on'].date() if parsed['announced_on'] else 'Unknown'}")
        print(f"    Investors: {', '.join(parsed['investors'][:3]) if parsed['investors'] else 'None listed'}")
        print(f"    Category: {parsed['category']}")
