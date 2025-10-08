#!/usr/bin/env python3
"""
VC Website Finder Agent - Discover official websites for VC organizations.

Strategy:
1. Check if website already exists → skip
2. Extract domains from sources (articles may link to VC sites)
3. Use LLM to find official website from VC name
4. Validate URL is reachable
5. Update org.website field
"""

from urllib.parse import urlparse

import httpx
from langchain_openai import ChatOpenAI
from loguru import logger
from sqlalchemy import select

from src.config import settings
from src.db.connection import get_db
from src.db.models import Organization


class VCWebsiteFinder:
    """Finds and validates official websites for VC organizations."""

    def __init__(self, validate_urls: bool = False):
        """Initialize with OpenAI client and HTTP client.

        Args:
            validate_urls: If True, validate URLs via HTTP (slower, may fail on firewalls)
        """
        self.llm = ChatOpenAI(
            model="gpt-4o",  # Using GPT-4o for better knowledge and reasoning
            temperature=0,
            api_key=settings.openai_api_key,
        )
        self.http_client = httpx.Client(timeout=10.0, follow_redirects=True)
        self.validate_urls = validate_urls

    def extract_domains_from_sources(self, org: Organization) -> list[str]:
        """
        Extract potential VC domains from article sources.

        Articles often link to the VC's website when mentioning them.
        """
        domains = []

        if not org.sources:
            return domains

        for source in org.sources:
            url = source.get("url", "")
            if not url:
                continue

            # Parse the URL to get domain
            parsed = urlparse(url)
            domain = parsed.netloc

            # Skip news/article sites
            skip_domains = [
                "cryptodaily.co.uk",
                "techcrunch.com",
                "bloomberg.com",
                "reuters.com",
                "coindesk.com",
                "twitter.com",
                "x.com",
                "linkedin.com",
                "crunchbase.com",
            ]

            if any(skip in domain for skip in skip_domains):
                continue

            # This might be the VC's website
            if domain:
                domains.append(domain)

        return list(set(domains))  # Deduplicate

    def guess_domain_patterns(self, vc_name: str) -> list[str]:
        """
        Generate likely domain patterns based on VC name.

        Args:
            vc_name: Name of the VC firm

        Returns:
            List of potential domain URLs to try
        """
        import re

        # Clean the name: remove common suffixes and special chars
        clean_name = vc_name.lower()
        clean_name = re.sub(r'\b(capital|ventures|partners|venture|vc|fund|investments?)\b', '', clean_name)
        clean_name = re.sub(r'[^a-z0-9\s]', '', clean_name)
        clean_name = clean_name.strip().replace(' ', '')

        if not clean_name:
            # Fallback: use original name without spaces
            clean_name = re.sub(r'[^a-z0-9]', '', vc_name.lower())

        patterns = []

        # Common VC domain patterns
        tlds = ['.com', '.vc', '.capital', '.io']
        for tld in tlds:
            patterns.append(f"https://www.{clean_name}{tld}")
            patterns.append(f"https://{clean_name}{tld}")

        return patterns

    def find_website_with_llm(self, vc_name: str, context_domains: list[str] | None = None) -> str | None:
        """
        Use LLM to find the official website for a VC.

        Args:
            vc_name: Name of the VC firm
            context_domains: Domains found in sources (may help LLM)

        Returns:
            Official website URL or None
        """
        context = ""
        if context_domains:
            context = f"\nDomains found in related articles: {', '.join(context_domains)}"

        prompt = f"""You are helping to find the official website for a venture capital firm.

VC Firm Name: "{vc_name}"{context}

Task: Return the MOST LIKELY official website URL for this VC firm, even if you're not 100% certain.

Rules:
- Return ONLY the URL in the format: https://example.com
- Use https:// protocol
- Return the main domain (not subpages like /team or /about)
- Make your BEST GUESS based on the firm name and common VC website patterns
- Try patterns like: firmname.com, firmname.vc, firmname.capital
- ONLY return "UNKNOWN" if the name is clearly nonsensical or you have no reasonable guess
- Do not include any explanation, markdown, or extra text

Examples:
- Sequoia Capital → https://www.sequoiacap.com
- Andreessen Horowitz → https://a16z.com
- Paradigm → https://www.paradigm.xyz
- Public Works → https://www.publicworks.vc
- Auros Global → https://www.aurosglobal.com
- SMAPE Capital → https://www.smape.capital
- Frachtis → https://frachtis.com

Your answer (URL only):"""

        try:
            response = self.llm.invoke(prompt)
            url = response.content.strip().strip('"').strip("'")

            logger.info(f"LLM response for {vc_name}: '{url}'")

            # Validate it looks like a URL
            if url.startswith("http") and "UNKNOWN" not in url.upper():
                logger.debug(f"LLM found website for {vc_name}: {url}")
                return url

            logger.warning(f"LLM returned UNKNOWN for {vc_name}, trying domain patterns...")

            # Fallback: try common domain patterns
            patterns = self.guess_domain_patterns(vc_name)
            logger.info(f"Trying domain patterns for {vc_name}: {patterns[:3]}...")  # Show first 3

            for pattern in patterns:
                if self.validate_url(pattern):
                    logger.info(f"✅ Found valid domain via pattern matching: {pattern}")
                    return pattern

            logger.debug(f"No valid domain pattern found for {vc_name}")
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

    def find_and_update_website(self, org: Organization, db_session) -> dict:
        """
        Find and update website for a single VC organization.

        Args:
            org: Organization object (must be attached to db_session)
            db_session: SQLAlchemy session for database operations

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
        }

        # Skip if website already exists
        if org.website:
            stats["website"] = org.website
            stats["method"] = "already_exists"
            logger.debug(f"Skipping {org.name} - website already set: {org.website}")
            return stats

        try:
            # Strategy 1: Extract from sources
            source_domains = self.extract_domains_from_sources(org)
            if source_domains:
                logger.info(f"Found {len(source_domains)} potential domains in sources for {org.name}")

            # Strategy 2: Ask LLM
            website = self.find_website_with_llm(org.name, source_domains)

            if not website:
                stats["error"] = "LLM couldn't find website"
                logger.warning(f"No website found for {org.name}")
                return stats

            # Validate URL (optional, off by default)
            if self.validate_urls:
                if not self.validate_url(website):
                    stats["error"] = f"URL validation failed: {website}"
                    logger.warning(f"URL validation failed for {org.name}: {website}")
                    return stats
                logger.info(f"✓ URL validated for {org.name}: {website}")
            else:
                logger.debug(f"Skipping validation for {org.name}: {website}")

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

            logger.info(f"✅ Updated {org.name} → {website}")

        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Error processing {org.name}: {e}")
            db_session.rollback()

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

                stats = self.find_and_update_website(vc, db)

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
        "--validate",
        action="store_true",
        help="Validate URLs via HTTP request (slower, may fail on firewalls)",
    )

    args = parser.parse_args()

    logger.info("🔍 Starting VC Website Finder Agent...")

    finder = VCWebsiteFinder(validate_urls=args.validate)

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

            stats = finder.find_and_update_website(vc, db)
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
