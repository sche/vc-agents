#!/usr/bin/env python3
"""
Add a few well-known VCs with websites for testing the crawler.
"""

import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import select

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.connection import get_db
from src.db.models import Organization
from src.utils.helpers import generate_org_uniq_key


def add_test_vcs():
    """Add well-known VCs with websites for testing."""
    test_vcs = [
        {
            "name": "Andreessen Horowitz",
            "website": "https://a16z.com",
            "description": "Venture capital firm backing bold entrepreneurs",
        },
        {
            "name": "Sequoia Capital",
            "website": "https://www.sequoiacap.com",
            "description": "Partner with bold founders to build legendary companies",
        },
        {
            "name": "Paradigm",
            "website": "https://www.paradigm.xyz",
            "description": "Crypto-focused investment firm",
        },
        {
            "name": "Multicoin Capital",
            "website": "https://multicoin.capital",
            "description": "Thesis-driven investment firm",
        },
        {
            "name": "Pantera Capital",
            "website": "https://panteracapital.com",
            "description": "First institutional investment firm focused on blockchain",
        },
    ]

    created = 0
    updated = 0

    with get_db() as db:
        for vc_data in test_vcs:
            uniq_key = generate_org_uniq_key(vc_data["name"], vc_data["website"])

            # Check if exists
            stmt = select(Organization).where(Organization.uniq_key == uniq_key)
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                # Update
                existing.website = vc_data["website"]
                existing.description = vc_data["description"]
                existing.kind = "vc"
                logger.info(f"Updated: {vc_data['name']}")
                updated += 1
            else:
                # Create
                org = Organization(
                    name=vc_data["name"],
                    kind="vc",
                    website=vc_data["website"],
                    description=vc_data["description"],
                    sources=[
                        {
                            "type": "manual",
                            "note": "Added for testing VC crawler",
                        }
                    ],
                    uniq_key=uniq_key,
                )
                db.add(org)
                logger.info(f"Created: {vc_data['name']}")
                created += 1

        db.commit()

    logger.info(f"\n✅ Test VCs added: {created} created, {updated} updated")


if __name__ == "__main__":
    logger.info("Adding test VCs with websites...")
    add_test_vcs()
