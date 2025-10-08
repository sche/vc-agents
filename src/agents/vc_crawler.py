#!/usr/bin/env python3
"""
VC Crawler Agent - Extract team members from VC websites.

Strategy:
1. Use org.sources to find website URLs
2. Find team/about pages using intelligent navigation
3. Extract people using OpenAI vision/text extraction
4. Save to people, roles_employment, evidence tables
"""

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from loguru import logger
from playwright.sync_api import sync_playwright
from sqlalchemy import select

from src.config import settings
from src.db.connection import get_db
from src.db.models import Evidence, Organization, Person, RoleEmployment


class VCCrawler:
    """Crawls VC websites to extract team member information."""

    def __init__(self):
        """Initialize the crawler with OpenAI client."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Good balance of speed/cost/quality
            temperature=0,
            api_key=settings.openai_api_key,
        )
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def get_website_from_sources(self, org: Organization) -> str | None:
        """Extract website URL from org.sources or org.website."""
        if org.website:
            return org.website

        # Check sources for website
        if org.sources:
            for source in org.sources:
                if source.get("type") == "defillama" and source.get("url"):
                    return source["url"]

        return None

    def find_team_page(self, browser, base_url: str) -> str | None:
        """
        Find the team/about page using intelligent navigation.

        Strategy:
        1. Check common paths first (/team, /about, /people)
        2. Use LLM to analyze navigation menu
        3. Try sitemap if available
        """
        page = browser.new_page()

        try:
            logger.info(f"Loading base URL: {base_url}")
            page.goto(base_url, wait_until="networkidle", timeout=30000)

            # Strategy 1: Try common paths
            common_paths = ["/team", "/about", "/people", "/about-us", "/leadership", "/our-team"]
            for path in common_paths:
                test_url = base_url.rstrip("/") + path
                try:
                    response = page.goto(test_url, wait_until="networkidle", timeout=10000)
                    if response and response.ok:
                        # Check if page has people-related content
                        content = page.content().lower()
                        if any(keyword in content for keyword in ["team", "partner", "analyst", "principal"]):
                            logger.info(f"Found team page at: {test_url}")
                            return test_url
                except Exception as e:
                    logger.debug(f"Path {path} not found: {e}")
                    continue

            # Strategy 2: Use LLM to analyze navigation
            page.goto(base_url, wait_until="networkidle")
            nav_links = page.eval_on_selector_all(
                "nav a, header a, [role='navigation'] a",
                """
                (links) => links.map(link => ({
                    text: link.innerText?.trim(),
                    href: link.href
                })).filter(link => link.text && link.href)
                """,
            )

            if nav_links:
                # Ask LLM to identify team page link
                prompt = f"""Given these navigation links from a VC website, identify the link most likely to lead to the team/about page.

Links:
{json.dumps(nav_links, indent=2)}

Return ONLY the href of the most likely team page link, or "NONE" if no suitable link exists.
Look for links with text like: team, about, people, partners, leadership, our team, etc.
"""
                response = self.llm.invoke(prompt)
                team_url = response.content.strip().strip('"')

                if team_url and team_url != "NONE" and team_url.startswith("http"):
                    logger.info(f"LLM found team page: {team_url}")
                    return team_url

            logger.warning(f"Could not find team page for {base_url}")
            return None

        except Exception as e:
            logger.error(f"Error finding team page: {e}")
            return None
        finally:
            page.close()

    def extract_people_from_page(self, browser, team_url: str, org_id: str) -> list[dict]:
        """
        Extract people from team page using OpenAI.

        Returns list of dicts with: name, title, profile_url, headshot_url
        """
        page = browser.new_page()

        try:
            logger.info(f"Extracting people from: {team_url}")
            page.goto(team_url, wait_until="networkidle", timeout=30000)

            # Wait longer for dynamic content (JavaScript rendering)
            page.wait_for_timeout(5000)

            # Take screenshot for evidence
            screenshot_path = self.screenshot_dir / f"org_{org_id}_{datetime.now().timestamp()}.png"
            page.screenshot(path=screenshot_path, full_page=True)

            # Get page HTML
            html_content = page.content()

            # Try to extract visible text with structure preserved
            # This reduces token count and improves LLM focus
            try:
                # Get all text content with some structure (headings, links)
                structured_text = page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, a, span, div[class*="team"], div[class*="person"], div[class*="member"]');
                        let text = '';
                        elements.forEach(el => {
                            const tag = el.tagName.toLowerCase();
                            const content = el.textContent?.trim();
                            if (content && content.length > 0 && content.length < 200) {
                                if (tag.startsWith('h')) {
                                    text += `\\n## ${content}\\n`;
                                } else if (tag === 'a' && el.href) {
                                    text += `[${content}](${el.href}) `;
                                } else {
                                    text += `${content} `;
                                }
                            }
                        });
                        return text;
                    }
                """)
            except Exception:
                structured_text = None

            # Improved prompt with examples
            prompt = f"""Extract all team members from this VC firm's team/about page.

For each person found, extract:
- name: Full name (e.g., "Kyle Samani", "Tushar Jain")
- title: Job title (e.g., "Managing Partner", "General Partner", "Principal", "Analyst")
- profile_url: Link to their profile page if present (look for href in links)
- headshot_url: Link to their photo if present (look for img src)

IMPORTANT:
1. Look for patterns like team member cards, bio sections, or lists of people
2. Names are typically in headings (h1-h6) or bold text
3. Titles often appear right after names
4. Return ONLY a valid JSON array of objects
5. If no team members found, return []

Example output format:
[
  {{"name": "Kyle Samani", "title": "Managing Partner", "profile_url": "/team/kyle-samani", "headshot_url": "/images/kyle.jpg"}},
  {{"name": "Tushar Jain", "title": "Managing Partner", "profile_url": null, "headshot_url": null}}
]

{"Structured content:" if structured_text else "HTML content (first 80KB):"}
{structured_text if structured_text else html_content[:80000]}

JSON array:"""

            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # Clean up markdown formatting if present
            if content.startswith("```"):
                content = re.sub(r"```json\s*|\s*```", "", content).strip()

            people_data = json.loads(content)

            logger.info(f"Extracted {len(people_data)} people from {team_url}")

            # Add metadata
            for person in people_data:
                person["source_url"] = team_url
                person["screenshot_path"] = str(screenshot_path)
                person["org_id"] = org_id

            return people_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error extracting people: {e}")
            return []
        finally:
            page.close()

    def save_person(self, person_data: dict, org_id: str, base_url: str) -> tuple[str | None, str]:
        """
        Save person to database and return (person_id, status).

        Returns:
            Tuple of (person_id, status) where status is one of:
            - "created": New person created
            - "updated": Existing person updated
            - "skipped": Existing person skipped (too recent)
        """
        with get_db() as db:
            # Check if person exists (by name + org_id to avoid collisions)
            # Same name at different VCs should be separate person records
            discovered_from_filter = Person.discovered_from['org_id'].astext == org_id
            stmt = select(Person).where(
                Person.full_name == person_data["name"],
                discovered_from_filter
            )
            existing_person = db.execute(stmt).scalar_one_or_none()

            # Convert relative URLs to absolute URLs
            profile_url = person_data.get("profile_url")
            if profile_url and not profile_url.startswith("http"):
                profile_url = base_url.rstrip("/") + "/" + profile_url.lstrip("/")

            headshot_url = person_data.get("headshot_url")
            if headshot_url and not headshot_url.startswith("http"):
                headshot_url = base_url.rstrip("/") + "/" + headshot_url.lstrip("/")

            if existing_person:
                # Check if we should update (based on recrawl_after_days setting)
                should_update = True
                if existing_person.updated_at:
                    days_since_update = (datetime.utcnow() - existing_person.updated_at.replace(tzinfo=None)).days
                    should_update = days_since_update >= settings.recrawl_after_days

                if not should_update:
                    logger.debug(
                        f"Skipping {person_data['name']} - last updated {days_since_update} days ago "
                        f"(threshold: {settings.recrawl_after_days} days)"
                    )
                    return str(existing_person.id), "skipped"

                # Update existing person with latest data
                existing_person.socials = {
                    **existing_person.socials,  # Keep existing socials
                    "profile_url": profile_url,
                    "headshot_url": headshot_url,
                }

                # Add to enrichment history
                if not existing_person.enrichment_history:
                    existing_person.enrichment_history = []

                existing_person.enrichment_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "vc_crawler_refresh",
                    "org_id": org_id,
                    "updated_fields": ["socials"],
                })

                logger.info(f"Updated person: {person_data['name']} (last update was {days_since_update} days ago)")
                return str(existing_person.id), "updated"

            # Create new person
            person = Person(
                full_name=person_data["name"],
                socials={
                    "profile_url": profile_url,
                    "headshot_url": headshot_url,
                },
                discovered_from={
                    "source": "vc_crawler",
                    "org_id": org_id,
                    "url": person_data.get("source_url"),
                },
            )
            db.add(person)
            db.flush()

            logger.info(f"Created person: {person_data['name']}")
            return str(person.id), "created"

    def save_role(self, person_id: str, org_id: str, title: str):
        """Save employment role to database."""
        with get_db() as db:
            # Check if role exists
            stmt = select(RoleEmployment).where(
                RoleEmployment.person_id == person_id,
                RoleEmployment.org_id == org_id,
                RoleEmployment.title == title,
            )
            existing_role = db.execute(stmt).scalar_one_or_none()

            if existing_role:
                logger.debug(f"Role already exists: {title}")
                return

            # Create new role
            role = RoleEmployment(
                person_id=person_id,
                org_id=org_id,
                title=title,
                is_current=True,  # Assume current unless we have end_date
            )
            db.add(role)
            logger.info(f"Created role: {title}")

    def save_evidence(self, person_id: str, person_data: dict, base_url: str):
        """Save extraction evidence to database."""
        # Convert relative URLs to absolute URLs for evidence
        profile_url = person_data.get("profile_url")
        if profile_url and not profile_url.startswith("http"):
            profile_url = base_url.rstrip("/") + "/" + profile_url.lstrip("/")

        headshot_url = person_data.get("headshot_url")
        if headshot_url and not headshot_url.startswith("http"):
            headshot_url = base_url.rstrip("/") + "/" + headshot_url.lstrip("/")

        with get_db() as db:
            evidence = Evidence(
                person_id=person_id,
                evidence_type="vc_crawler_extraction",
                url=person_data["source_url"],
                screenshot_url=person_data.get("screenshot_path"),
                extracted_data={
                    "name": person_data["name"],
                    "title": person_data.get("title"),
                    "profile_url": profile_url,
                    "headshot_url": headshot_url,
                    "confidence": 0.9,  # High confidence for direct extraction
                },
                extraction_method="openai_gpt4o_mini",
            )
            db.add(evidence)
            logger.debug(f"Saved evidence for: {person_data['name']}")

    def crawl_vc(self, org: Organization) -> dict:
        """
        Crawl a single VC organization.

        Returns stats dict with counts.
        """
        stats = {
            "org_name": org.name,
            "people_found": 0,
            "people_created": 0,
            "people_updated": 0,
            "people_skipped": 0,
            "roles_created": 0,
            "error": None,
        }

        try:
            # Get website
            website = self.get_website_from_sources(org)
            if not website:
                stats["error"] = "No website found"
                logger.warning(f"No website for {org.name}")
                return stats

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    # Find team page
                    team_url = self.find_team_page(browser, website)
                    if not team_url:
                        stats["error"] = "Team page not found"
                        return stats

                    # Extract people
                    people_data = self.extract_people_from_page(browser, team_url, str(org.id))
                    stats["people_found"] = len(people_data)

                    # Save to database
                    for person_data in people_data:
                        person_id, status = self.save_person(person_data, str(org.id), website)

                        if person_id:
                            if status == "created":
                                stats["people_created"] += 1
                            elif status == "updated":
                                stats["people_updated"] += 1
                            elif status == "skipped":
                                stats["people_skipped"] += 1

                            # Save role if title exists (only for created/updated, not skipped)
                            if status != "skipped" and person_data.get("title"):
                                self.save_role(person_id, str(org.id), person_data["title"])
                                stats["roles_created"] += 1

                            # Save evidence (only for created/updated, not skipped)
                            if status != "skipped":
                                self.save_evidence(person_id, person_data, website)

                    # Commit all changes
                    with get_db() as db:
                        db.commit()

                    logger.info(
                        f"✅ {org.name}: {stats['people_created']} created, "
                        f"{stats['people_updated']} updated, {stats['people_skipped']} skipped, "
                        f"{stats['roles_created']} roles"
                    )

                finally:
                    browser.close()

        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Error crawling {org.name}: {e}")

        return stats

    def crawl_all_vcs(self, limit: int | None = None) -> dict:
        """
        Crawl all VCs in database.

        Args:
            limit: Maximum number of VCs to crawl (None = all)

        Returns:
            Overall statistics
        """
        # Get all VCs
        with get_db() as db:
            stmt = select(Organization).where(Organization.kind == "vc")
            if limit:
                stmt = stmt.limit(limit)
            vcs = db.execute(stmt).scalars().all()

        logger.info(f"Found {len(vcs)} VCs to crawl")

        overall_stats = {
            "total_vcs": len(vcs),
            "vcs_processed": 0,
            "people_created": 0,
            "people_updated": 0,
            "people_skipped": 0,
            "total_roles": 0,
            "errors": [],
        }

        for i, vc in enumerate(vcs, 1):
            logger.info(f"\n[{i}/{len(vcs)}] Crawling: {vc.name}")

            stats = self.crawl_vc(vc)
            overall_stats["vcs_processed"] += 1
            overall_stats["people_created"] += stats["people_created"]
            overall_stats["people_updated"] += stats["people_updated"]
            overall_stats["people_skipped"] += stats["people_skipped"]
            overall_stats["total_roles"] += stats["roles_created"]

            if stats["error"]:
                overall_stats["errors"].append(f"{vc.name}: {stats['error']}")

        return overall_stats


def main():
    """Main entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Crawl VC websites for team information")
    parser.add_argument("--limit", type=int, help="Limit number of VCs to crawl")
    parser.add_argument("--vc-name", type=str, help="Crawl specific VC by name")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help=f"Force refresh all people, ignoring the {settings.recrawl_after_days}-day threshold",
    )

    args = parser.parse_args()

    # Override recrawl setting if force-refresh is set
    if args.force_refresh:
        logger.info("🔄 Force refresh mode enabled - will update all people regardless of age")
        settings.recrawl_after_days = 0

    logger.info("🕷️  Starting VC Crawler Agent...")

    crawler = VCCrawler()

    if args.vc_name:
        # Crawl specific VC
        with get_db() as db:
            stmt = select(Organization).where(
                Organization.kind == "vc", Organization.name.ilike(f"%{args.vc_name}%")
            )
            vc = db.execute(stmt).scalar_one_or_none()

            if not vc:
                logger.error(f"VC not found: {args.vc_name}")
                return

            stats = crawler.crawl_vc(vc)
            logger.info(f"\n📊 Results: {json.dumps(stats, indent=2)}")
    else:
        # Crawl all VCs
        stats = crawler.crawl_all_vcs(limit=args.limit)

        logger.info("\n" + "=" * 60)
        logger.info("📊 Crawl Summary:")
        logger.info(f"   VCs processed: {stats['vcs_processed']}/{stats['total_vcs']}")
        logger.info(f"   People created: {stats['people_created']}")
        logger.info(f"   People updated: {stats['people_updated']}")
        logger.info(f"   People skipped: {stats['people_skipped']} (within {settings.recrawl_after_days}-day threshold)")
        logger.info(f"   Roles created: {stats['total_roles']}")

        if stats["errors"]:
            logger.warning(f"\n⚠️  Errors ({len(stats['errors'])}):")
            for error in stats["errors"]:
                logger.warning(f"   - {error}")

        logger.info("=" * 60)


if __name__ == "__main__":
    main()
