"""
Deals Ingestor Agent - LangGraph 1.0 with SQLAlchemy ORM

Loads VC deals from DefiLlama, creates/updates orgs and deals using proper ORM models.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from sqlalchemy import select
from typing_extensions import TypedDict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after path is set
from src.clients.defillama import DefiLlamaLoader  # noqa: E402
from src.db.connection import get_db  # noqa: E402
from src.db.models import Deal, Organization  # noqa: E402
from src.utils.helpers import (  # noqa: E402
    generate_deal_uniq_hash,
    generate_org_uniq_key,
    normalize_company_name,
)


class IngestorState(TypedDict):
    """State for deals ingestor agent."""

    batch_size: int
    deals_loaded: int
    orgs_created: int
    deals_created: int
    errors: list[str]
    status: str
    current_deal: dict | None


def load_deals_node(state: IngestorState) -> Command[Literal["process_deal", "finish"]]:
    """Load recent deals from DefiLlama."""
    try:
        loader = DefiLlamaLoader()
        all_raises = loader.load_raises()
        recent_raises = loader.filter_by_date(all_raises, since_days=90)

        batch_size = state.get("batch_size", 10)
        deals = recent_raises[:batch_size]

        if not deals:
            return Command(
                goto="finish",
                update={"status": "No deals to process", "deals_loaded": 0},
            )

        return Command(
            goto="process_deal",
            update={
                "status": f"Loaded {len(deals)} deals",
                "deals_loaded": len(deals),
                "current_deal": deals[0] if deals else None,
            },
        )

    except Exception as e:
        return Command(
            goto="finish",
            update={
                "status": "Error loading deals",
                "errors": state.get("errors", []) + [str(e)],
            },
        )


def process_deal_node(state: IngestorState) -> Command[Literal["create_org", "finish"]]:
    """Process a single deal - extract organization info."""
    deal = state.get("current_deal")

    if not deal:
        return Command(goto="finish", update={"status": "No more deals to process"})

    try:
        # Parse the deal using the loader
        loader = DefiLlamaLoader()
        parsed = loader.parse_raise(deal)

        # Extract org info
        org_name = parsed["project_name"]
        normalized_name = normalize_company_name(org_name)

        # Determine org kind based on category
        category = parsed.get("category", "")
        kind = "startup" if category else "startup"  # Default to startup for now

        return Command(
            goto="create_org",
            update={
                "status": f"Processing {org_name}",
                "current_deal": {
                    **deal,
                    "_parsed": parsed,
                    "_org_name": org_name,
                    "_normalized_name": normalized_name,
                    "_kind": kind,
                },
            },
        )

    except Exception as e:
        errors = state.get("errors", [])
        return Command(
            goto="finish",
            update={
                "status": "Error processing deal",
                "errors": errors + [f"Process deal: {str(e)}"],
            },
        )


def create_org_node(state: IngestorState) -> Command[Literal["create_deal", "finish"]]:
    """Create or update organization using SQLAlchemy ORM."""
    deal = state.get("current_deal")

    if not deal or "_parsed" not in deal:
        return Command(goto="finish", update={"status": "Missing parsed data"})

    parsed = deal["_parsed"]
    org_name = deal["_org_name"]
    kind = deal["_kind"]

    try:
        # Generate unique key for deduplication
        uniq_key = generate_org_uniq_key(org_name)

        with get_db() as db:
            # Check if org exists
            stmt = select(Organization).where(Organization.uniq_key == uniq_key)
            existing_org = db.execute(stmt).scalar_one_or_none()

            if existing_org:
                # Update existing
                existing_org.focus = parsed.get("chains", [])
                existing_org.sources = existing_org.sources + [
                    {
                        "type": "defillama",
                        "url": parsed.get("source_url", ""),
                        "imported_at": datetime.utcnow().isoformat(),
                    }
                ]
                org_id = existing_org.id
            else:
                # Create new
                org = Organization(
                    name=org_name,
                    kind=kind,
                    description=None,
                    focus=parsed.get("chains", []),
                    sources=[
                        {
                            "type": "defillama",
                            "url": parsed.get("source_url", ""),
                            "imported_at": datetime.utcnow().isoformat(),
                        }
                    ],
                    uniq_key=uniq_key,
                )
                db.add(org)
                db.flush()  # Get the ID
                org_id = org.id

            orgs_created = state.get("orgs_created", 0) + (1 if not existing_org else 0)

            return Command(
                goto="create_deal",
                update={
                    "status": f"Created/updated org {org_name}",
                    "orgs_created": orgs_created,
                    "current_deal": {**deal, "_org_id": org_id},
                },
            )

    except Exception as e:
        errors = state.get("errors", [])
        return Command(
            goto="finish",
            update={
                "status": "Error creating org",
                "errors": errors + [f"Create org: {str(e)}"],
            },
        )


def create_deal_node(state: IngestorState) -> Command[Literal["finish"]]:
    """Create deal record using SQLAlchemy ORM."""
    deal = state.get("current_deal")

    if not deal or "_org_id" not in deal or "_parsed" not in deal:
        return Command(goto="finish", update={"status": "Missing org ID or parsed data"})

    org_id = deal["_org_id"]
    parsed = deal["_parsed"]

    try:
        # Get org name for hash generation
        org_name = deal["_org_name"]

        # Generate unique hash for deal idempotency
        announced_date = parsed["announced_on"] if parsed.get("announced_on") else datetime.now()
        uniq_hash = generate_deal_uniq_hash(
            org_name,
            announced_date,
            parsed.get("round"),
            parsed.get("amount_usd"),
        )

        with get_db() as db:
            # Check if deal exists
            stmt = select(Deal).where(Deal.uniq_hash == uniq_hash)
            existing_deal = db.execute(stmt).scalar_one_or_none()

            if not existing_deal:
                # Create new deal
                new_deal = Deal(
                    org_id=org_id,
                    round=parsed.get("round"),
                    amount_eur=parsed.get("amount_usd"),  # TODO: convert to EUR
                    amount_original=parsed.get("amount_usd"),
                    currency_original="USD",
                    announced_on=announced_date.date() if announced_date else None,
                    investors=parsed.get("investors", []),
                    source={
                        "type": "defillama",
                        "url": parsed.get("source_url", ""),
                        "imported_at": datetime.utcnow().isoformat(),
                    },
                    uniq_hash=uniq_hash,
                )
                db.add(new_deal)

                deals_created = state.get("deals_created", 0) + 1
            else:
                deals_created = state.get("deals_created", 0)

            return Command(
                goto="finish",
                update={
                    "status": f"Created deal for org {org_id}",
                    "deals_created": deals_created,
                },
            )

    except Exception as e:
        errors = state.get("errors", [])
        return Command(
            goto="finish",
            update={
                "status": "Error creating deal",
                "errors": errors + [f"Create deal: {str(e)}"],
            },
        )


def finish_node(state: IngestorState) -> Command:
    """Finish processing."""
    return Command(goto=END, update={"status": "Processing complete"})


def build_ingestor_graph() -> StateGraph:
    """Build the deals ingestor graph."""
    graph = StateGraph(IngestorState)

    # Add nodes
    graph.add_node("load_deals", load_deals_node)
    graph.add_node("process_deal", process_deal_node)
    graph.add_node("create_org", create_org_node)
    graph.add_node("create_deal", create_deal_node)
    graph.add_node("finish", finish_node)

    # Set entry point
    graph.add_edge(START, "load_deals")

    return graph


def run_ingestor(batch_size: int = 5) -> dict:
    """Run the deals ingestor agent."""
    graph = build_ingestor_graph()
    app = graph.compile()

    initial_state = {
        "batch_size": batch_size,
        "deals_loaded": 0,
        "orgs_created": 0,
        "deals_created": 0,
        "errors": [],
        "status": "Starting",
        "current_deal": None,
    }

    result = app.invoke(initial_state)
    return result


if __name__ == "__main__":
    print("\n🚀 Running Deals Ingestor Agent (LangGraph 1.0 + SQLAlchemy ORM)...\n")

    result = run_ingestor(batch_size=5)

    print("📊 Results:")
    print(f"   Status: {result['status']}")
    print(f"   Deals loaded: {result['deals_loaded']}")
    print(f"   Orgs created: {result['orgs_created']}")
    print(f"   Deals created: {result['deals_created']}")

    if result.get("errors"):
        print(f"\n⚠️  Errors ({len(result['errors'])}):")
        for error in result["errors"]:
            print(f"   - {error}")

    print()
