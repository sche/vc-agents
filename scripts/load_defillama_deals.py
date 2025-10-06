#!/usr/bin/env python3
"""
Load deals from DefiLlama into the database.

Simple ETL script - no agents needed for this straightforward task.
"""

import sys
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import select

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.defillama import DefiLlamaLoader
from src.db.connection import get_db
from src.db.models import Deal, Organization
from src.utils.helpers import (
    generate_deal_uniq_hash,
    generate_org_uniq_key,
)


def create_or_update_org(parsed_deal: dict) -> str:
    """Create or update organization from parsed deal. Returns org_id."""
    org_name = parsed_deal["project_name"]

    # Generate unique key for deduplication (using name only, no website from DefiLlama)
    uniq_key = generate_org_uniq_key(org_name, website=None)

    with get_db() as db:
        # Check if org exists by uniq_key
        stmt = select(Organization).where(Organization.uniq_key == uniq_key)
        existing_org = db.execute(stmt).scalar_one_or_none()

        if existing_org:
            # Update sources if org exists
            existing_org.focus = parsed_deal.get("chains", [])
            existing_org.sources = existing_org.sources + [
                {
                    "type": "defillama",
                    "url": parsed_deal.get("source_url", ""),
                    "imported_at": datetime.utcnow().isoformat(),
                }
            ]
            logger.info(f"Updated org: {org_name}")
            org_id = str(existing_org.id)
            return org_id
        else:
            # Create new org
            org = Organization(
                name=org_name,
                kind="startup",  # Default to startup for DefiLlama deals
                description=None,
                focus=parsed_deal.get("chains", []),
                sources=[
                    {
                        "type": "defillama",
                        "url": parsed_deal.get("source_url", ""),
                        "imported_at": datetime.utcnow().isoformat(),
                    }
                ],
                uniq_key=uniq_key,
            )
            db.add(org)
            db.flush()  # Get the ID
            org_id = str(org.id)
            logger.info(f"Created org: {org_name}")
            return org_id


def create_deal(org_id: str, parsed_deal: dict) -> Deal | None:
    """Create deal if it doesn't exist."""
    org_name = parsed_deal["project_name"]

    # Get amount and handle None
    amount_usd = parsed_deal.get("amount_usd")
    # Skip deals without amount information
    if amount_usd is None:
        logger.debug(f"Skipping deal without amount: {org_name} - {parsed_deal.get('round')}")
        return None

    # Generate unique hash for idempotency
    announced_date = parsed_deal["announced_on"] if parsed_deal.get("announced_on") else datetime.now()
    uniq_hash = generate_deal_uniq_hash(
        org_name,
        announced_date,
        parsed_deal.get("round"),
        amount_usd,
    )

    with get_db() as db:
        # Check if deal exists
        stmt = select(Deal).where(Deal.uniq_hash == uniq_hash)
        existing_deal = db.execute(stmt).scalar_one_or_none()

        if existing_deal:
            logger.debug(f"Deal already exists: {org_name} - {parsed_deal.get('round')}")
            return None

        # Create new deal
        deal = Deal(
            org_id=org_id,
            round=parsed_deal.get("round"),
            amount_usd=amount_usd,
            amount_original=parsed_deal.get("amount_usd"),
            currency_original="USD",
            announced_on=announced_date.date() if announced_date else None,
            investors=parsed_deal.get("investors", []),
            source={
                "type": "defillama",
                "url": parsed_deal.get("source_url", ""),
                "imported_at": datetime.utcnow().isoformat(),
            },
            uniq_hash=uniq_hash,
        )
        db.add(deal)
        logger.info(f"Created deal: {org_name} - {parsed_deal.get('round')} - ${parsed_deal.get('amount_usd')}M")
        return deal


def load_deals(since_days: int = 90, limit: int | None = None) -> dict:
    """
    Load deals from DefiLlama and insert into database.

    Args:
        since_days: Only load deals from last N days
        limit: Maximum number of deals to process (None = all)

    Returns:
        Dictionary with statistics
    """
    logger.info(f"Loading deals from last {since_days} days...")

    # Load and filter deals
    loader = DefiLlamaLoader()
    all_raises = loader.load_raises()
    recent_deals = loader.filter_by_date(all_raises, since_days=since_days)

    if limit:
        recent_deals = recent_deals[:limit]

    logger.info(f"Found {len(recent_deals)} deals to process")

    # Track stats
    stats = {
        "total_deals": len(recent_deals),
        "orgs_created": 0,
        "orgs_updated": 0,
        "deals_created": 0,
        "deals_skipped": 0,
        "errors": [],
    }

    # Process each deal
    for i, deal_data in enumerate(recent_deals, 1):
        try:
            # Parse deal
            parsed = loader.parse_raise(deal_data)

            # Track existing org count
            with get_db() as db:
                org_count_before = db.query(Organization).count()

            # Create/update org and get org_id
            org_id = create_or_update_org(parsed)

            # Track if org was created or updated
            with get_db() as db:
                org_count_after = db.query(Organization).count()
                if org_count_after > org_count_before:
                    stats["orgs_created"] += 1
                else:
                    stats["orgs_updated"] += 1

            # Create deal
            deal = create_deal(org_id, parsed)
            if deal:
                stats["deals_created"] += 1
            else:
                stats["deals_skipped"] += 1

            # Progress update every 10 deals
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(recent_deals)} deals processed")

        except Exception as e:
            error_msg = f"Error processing deal {i}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            continue

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Load DefiLlama deals into database")
    parser.add_argument(
        "--since-days",
        type=int,
        default=90,
        help="Load deals from last N days (default: 90)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of deals to process (default: all)",
    )

    args = parser.parse_args()

    logger.info("🚀 Starting DefiLlama deals loader...")

    stats = load_deals(since_days=args.since_days, limit=args.limit)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Load Summary:")
    logger.info(f"   Total deals processed: {stats['total_deals']}")
    logger.info(f"   Orgs created: {stats['orgs_created']}")
    logger.info(f"   Orgs updated: {stats['orgs_updated']}")
    logger.info(f"   Deals created: {stats['deals_created']}")
    logger.info(f"   Deals skipped (duplicates): {stats['deals_skipped']}")

    if stats["errors"]:
        logger.warning(f"\n⚠️  Errors ({len(stats['errors'])}):")
        for error in stats["errors"]:
            logger.warning(f"   - {error}")

    logger.info("=" * 60 + "\n")

    if stats["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
