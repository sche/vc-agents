#!/usr/bin/env python3
"""
VC Website Finder Agent - Discover official websites for VC organizations.

Strategy:
1. Check if website already exists → skip
2. Extract article URLs from sources (for LLM context)
3. Use LLM to find official website from VC name + article context
4. Validate URL is reachable
5. Update org.website field
"""

import httpx
from langchain_openai import ChatOpenAI
from loguru import logger
from sqlalchemy import select

from src.config import settings
from src.db.connection import get_db
from src.db.models import AgentRun, Organization


class VCWebsiteFinder:
    """Finds and validates official websites for VC organizations."""

    def __init__(self, use_perplexity: bool = True):
        """Initialize with LLM client and HTTP client.

        Args:
            use_perplexity: If True (default), use Perplexity AI (has real-time web search).
                          If False, use OpenAI GPT.
        """
        if use_perplexity and settings.perplexity_api_key:
            # Perplexity has real-time web search capabilities
            self.llm = ChatOpenAI(
                model="sonar",  # Perplexity's online search model
                temperature=0.5,
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai",
            )
            self.llm_provider = "perplexity"
            logger.info("Using Perplexity AI with real-time web search")
        else:
            # Fallback to OpenAI GPT
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.5,
                api_key=settings.openai_api_key,
            )
            self.llm_provider = "openai"
            logger.info("Using OpenAI GPT-4o")

        self.http_client = httpx.Client(timeout=10.0, follow_redirects=True)

    def create_agent_run(self, db_session, org_id: str, org_name: str, input_params: dict) -> str:
        """
        Create an agent run record to track the website finding process.

        Args:
            db_session: SQLAlchemy session
            org_id: Organization UUID
            org_name: Organization name
            input_params: Additional input parameters

        Returns:
            Run ID (UUID as string)
        """
        agent_run = AgentRun(
            agent_name="vc_website_finder",
            status="running",
            input_params={
                "org_id": str(org_id),
                "org_name": org_name,
                **input_params,
            },
        )
        db_session.add(agent_run)
        db_session.commit()
        return str(agent_run.id)

    def complete_agent_run(
        self,
        db_session,
        run_id: str,
        status: str,
        output_summary: dict,
        error_message: str | None = None,
    ):
        """
        Update agent run record on completion.

        Args:
            db_session: SQLAlchemy session
            run_id: Run ID from create_agent_run
            status: 'completed' or 'failed'
            output_summary: Dictionary with results
            error_message: Error message if failed
        """
        from datetime import datetime, timezone

        agent_run = db_session.get(AgentRun, run_id)
        if agent_run:
            agent_run.status = status
            agent_run.output_summary = output_summary
            agent_run.error_message = error_message
            agent_run.completed_at = datetime.now(timezone.utc)
            db_session.commit()


    def extract_urls_from_sources(self, org: Organization) -> list[str]:
        """
        Extract article URLs from sources to provide context to the LLM.

        These are news articles about deals mentioning the VC.
        The LLM can use these URLs as context to identify which VC we're looking for.
        """
        urls = []

        if not org.sources:
            return urls

        for source in org.sources:
            url = source.get("url", "")
            if url:
                urls.append(url)

        return list(set(urls))  # Deduplicate

    def find_website_with_llm(self, vc_name: str, context_urls: list[str]) -> str | None:
        """Use LLM to find the official website for a VC firm with validation.

        Returns the URL only if:
        1. LLM can confidently suggest a URL (not "UNKNOWN")
        2. The URL passes HTTP validation (is reachable)

        If either condition fails, returns None to indicate manual research is needed.
        This prevents false positives from domain guessing.
        """

        # Build context from URLs
        context = ""
        if context_urls:
            context = f"\n\nContext: This VC was mentioned in articles with these URLs: {', '.join(context_urls)}"

        prompt = f"""You are helping to find the official website for a venture capital firm.

VC Firm Name: "{vc_name}"

Task: Return the official, primary website URL for this VC firm.

Rules:
- Return ONLY the URL in the format: https://example.com
- Use https:// protocol
- Return the main domain (not subpages like /team or /about)
- Use your knowledge to find the most likely official website
- If you absolutely cannot find it, return "UNKNOWN"

Examples:
- Sequoia Capital → https://www.sequoiacap.com
- Andreessen Horowitz → https://a16z.com
- Paradigm → https://www.paradigm.xyz
{context}

Your answer (URL only):"""

        try:
            logger.debug(f"LLM prompt for {vc_name}:\n{prompt}")
            response = self.llm.invoke(prompt)
            url = response.content.strip()

            if url == "UNKNOWN":
                logger.info(f"LLM could not find website for {vc_name}")
                return None

            # Validate the LLM suggestion
            logger.info(f"LLM response for {vc_name}: '{url}'")
            if self.validate_url(url):
                logger.info(f"✓ URL validated: {url}")
                return url
            else:
                logger.warning(f"✗ LLM suggested URL is not reachable: {url}")
                logger.warning(f"Manual research needed for {vc_name} - LLM suggestion failed validation")
                return None

        except Exception as e:
            logger.error(f"Error calling LLM for {vc_name}: {e}")
            return None

    def validate_url(self, url: str) -> bool:
        """
        Check if URL is reachable and returns a valid response.

        Args:
            url: Website URL to validate

        Returns:
            True if URL is valid and reachable
        """
        try:
            response = self.http_client.get(url)

            # Accept 200-399 status codes
            if 200 <= response.status_code < 400:
                logger.debug(f"✓ URL validated: {url} (status: {response.status_code})")
                return True

            logger.warning(f"✗ URL returned {response.status_code}: {url}")
            return False

        except Exception as e:
            logger.warning(f"✗ URL validation failed for {url}: {e}")
            return False

    def find_and_update_website(self, org: Organization, db_session, force: bool = False) -> dict:
        """
        Find and update website for a single VC organization.

        Args:
            org: Organization object (must be attached to db_session)
            db_session: SQLAlchemy session for database operations
            force: If True, re-find website even if already set (will validate existing URL first)

        Returns:
            Stats dict with result
        """
        stats = {
            "org_name": org.name,
            "found": False,
            "updated": False,
            "website": None,
            "method": None,
            "error": None,
            "run_id": None,
        }

        # Create agent run to track this workflow
        run_id = self.create_agent_run(
            db_session,
            org.id,
            org.name,
            {"force": force},
        )
        stats["run_id"] = run_id

        # Check if website already exists
        if org.website:
            if not force:
                # Not forcing, skip this VC
                stats["website"] = org.website
                stats["method"] = "already_exists"
                logger.debug(f"Skipping {org.name} - website already set: {org.website}")

                # Mark run as completed
                self.complete_agent_run(
                    db_session,
                    run_id,
                    "completed",
                    {
                        "website": org.website,
                        "method": "already_exists",
                        "message": "Website already set, skipped",
                    },
                )
                return stats
            else:
                # Forcing, validate existing URL first
                logger.info(f"Force mode: Validating existing URL for {org.name}: {org.website}")
                if self.validate_url(org.website):
                    logger.info(f"✅ Existing URL is valid, keeping it: {org.website}")
                    stats["website"] = org.website
                    stats["method"] = "validated_existing"
                    stats["found"] = True

                    # Mark run as completed
                    self.complete_agent_run(
                        db_session,
                        run_id,
                        "completed",
                        {
                            "website": org.website,
                            "method": "validated_existing",
                            "message": "Existing URL validated successfully",
                        },
                    )
                    return stats
                else:
                    logger.warning(f"❌ Existing URL is invalid, will try to find new one: {org.website}")
                    # Clear the invalid URL so we can find a new one
                    org.website = None

        try:
            # Strategy 1: Extract from sources
            source_urls = self.extract_urls_from_sources(org)
            if source_urls:
                logger.info(f"Found {len(source_urls)} potential URLs in sources for {org.name}")

            # Strategy 2: Ask LLM (with automatic validation)
            website = self.find_website_with_llm(org.name, source_urls)

            if not website:
                stats["error"] = "No valid website found (LLM + patterns failed)"
                logger.warning(f"❌ No valid website found for {org.name}")

                # Mark run as failed
                self.complete_agent_run(
                    db_session,
                    run_id,
                    "failed",
                    {
                        "website": None,
                        "method": "llm_with_fallback",
                        "source_urls_tried": source_urls,
                    },
                    error_message="No valid website found (LLM + pattern matching failed)",
                )
                return stats

            # URL is already validated by find_website_with_llm
            logger.info(f"✓ Found and validated website for {org.name}: {website}")

            # Update org (session will commit later)
            org.website = website

            # Add to sources
            if not org.sources:
                org.sources = []

            org.sources.append({
                "type": "vc_website_finder",
                "url": website,
                "method": "llm_discovery",
                "validated": True,
            })

            db_session.commit()

            stats["found"] = True
            stats["updated"] = True
            stats["website"] = website
            stats["method"] = "llm_discovery"

            # Mark run as completed
            self.complete_agent_run(
                db_session,
                run_id,
                "completed",
                {
                    "website": website,
                    "method": "llm_discovery",
                    "validated": True,
                    "source_urls_tried": source_urls,
                },
            )

            logger.info(f"✅ Updated {org.name} → {website}")

        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Error processing {org.name}: {e}")
            db_session.rollback()

            # Mark run as failed
            self.complete_agent_run(
                db_session,
                run_id,
                "failed",
                {
                    "website": None,
                    "error": str(e),
                },
                error_message=str(e),
            )

        return stats

    def find_all_vc_websites(self, limit: int | None = None, force: bool = False) -> dict:
        """
        Find websites for all VCs without websites.

        Args:
            limit: Maximum number of VCs to process
            force: If True, re-find websites even if already set

        Returns:
            Overall statistics
        """
        # Get VC IDs to process (avoid detached instance errors)
        with get_db() as db:
            stmt = select(Organization.id, Organization.name).where(Organization.kind == "vc")

            if not force:
                stmt = stmt.where(Organization.website.is_(None))

            if limit:
                stmt = stmt.limit(limit)

            vc_data = db.execute(stmt).all()

        logger.info(f"Found {len(vc_data)} VCs to process")

        overall_stats = {
            "total_vcs": len(vc_data),
            "websites_found": 0,
            "already_had_website": 0,
            "validation_failed": 0,
            "llm_failed": 0,
            "errors": [],
        }

        for i, (vc_id, vc_name) in enumerate(vc_data, 1):
            logger.info(f"\n[{i}/{len(vc_data)}] Processing: {vc_name}")

            # Reload the org in a fresh session
            with get_db() as db:
                vc = db.execute(
                    select(Organization).where(Organization.id == vc_id)
                ).scalar_one()

                stats = self.find_and_update_website(vc, db, force)

                if stats["method"] == "already_exists":
                    overall_stats["already_had_website"] += 1
                elif stats["found"]:
                    overall_stats["websites_found"] += 1
                elif stats["error"]:
                    if "validation failed" in stats["error"]:
                        overall_stats["validation_failed"] += 1
                    elif "couldn't find" in stats["error"]:
                        overall_stats["llm_failed"] += 1

                    overall_stats["errors"].append(f"{vc_name}: {stats['error']}")

        return overall_stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Find official websites for VC organizations")
    parser.add_argument("--limit", type=int, help="Limit number of VCs to process")
    parser.add_argument("--vc-name", type=str, help="Process specific VC by name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-find websites even if already set",
    )
    parser.add_argument(
        "--no-perplexity",
        action="store_true",
        help="Use OpenAI GPT instead of Perplexity AI (Perplexity is default)",
    )

    args = parser.parse_args()

    logger.info("🔍 Starting VC Website Finder Agent...")
    logger.info("   ✓ URL validation: ENABLED (always)")
    logger.info("   ✓ Strategy: LLM-only (no pattern guessing)")

    finder = VCWebsiteFinder(use_perplexity=not args.no_perplexity)

    if args.vc_name:
        # Process specific VC
        with get_db() as db:
            stmt = select(Organization).where(
                Organization.kind == "vc",
                Organization.name.ilike(f"%{args.vc_name}%")
            )
            vc = db.execute(stmt).scalar_one_or_none()

            if not vc:
                logger.error(f"VC not found: {args.vc_name}")
                return

            stats = finder.find_and_update_website(vc, db, args.force)
            logger.info(f"\n📊 Result: {stats}")
    else:
        # Process all VCs
        stats = finder.find_all_vc_websites(limit=args.limit, force=args.force)

        logger.info("\n" + "=" * 60)
        logger.info("📊 Website Discovery Summary:")
        logger.info(f"   VCs processed: {stats['total_vcs']}")
        logger.info(f"   Websites found: {stats['websites_found']}")
        logger.info(f"   Already had website: {stats['already_had_website']}")
        logger.info(f"   LLM failed: {stats['llm_failed']}")
        logger.info(f"   Validation failed: {stats['validation_failed']}")

        if stats["errors"]:
            logger.warning(f"\n⚠️  Issues ({len(stats['errors'])}):")
            for error in stats["errors"][:10]:  # Show first 10
                logger.warning(f"   - {error}")

        logger.info("=" * 60)


if __name__ == "__main__":
    main()
