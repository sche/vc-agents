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
import uuid
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from loguru import logger
from playwright.sync_api import sync_playwright
from sqlalchemy import select

from src.config import settings
from src.db.connection import get_db
from src.db.models import AgentRun, Evidence, Organization, Person, RoleEmployment


class VCCrawler:
    """Crawls VC websites to extract team member information."""

    def __init__(self, use_fallback: bool = True):
        """Initialize the crawler with OpenAI client.

        Args:
            use_fallback: If True, use Perplexity fallback when GPT-4o-mini finds 0 people
        """
        self.llm_mini = ChatOpenAI(
            model="gpt-4o-mini",  # Fast, cheap for initial extraction
            temperature=0,
            api_key=settings.openai_api_key,
        )
        # Use Perplexity for fallback (real-time web search)
        self.llm_fallback = ChatOpenAI(
            model="sonar",  # Perplexity's real-time search model
            temperature=0.5,
            api_key=settings.perplexity_api_key,
            base_url="https://api.perplexity.ai",
        )
        self.use_fallback = use_fallback
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
                response = self.llm_mini.invoke(prompt)
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

    def extract_people_from_page(self, browser, team_url: str, org_id: str, org_name: str = "Unknown") -> list[dict]:
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

            # Take screenshot for evidence (with error handling for Railway)
            screenshot_path = None
            try:
                screenshot_path = self.screenshot_dir / f"org_{org_id}_{datetime.now().timestamp()}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Screenshot saved: {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to take screenshot (continuing anyway): {e}")
                screenshot_path = None

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

            response = self.llm_mini.invoke(prompt)
            content = response.content.strip()

            # Clean up markdown formatting if present
            if content.startswith("```"):
                content = re.sub(r"```json\s*|\s*```", "", content).strip()

            people_data = json.loads(content)

            logger.info(f"GPT-4o-mini extracted {len(people_data)} people from {team_url}")

            # Fallback to Perplexity if mini found 0 people
            if len(people_data) == 0 and self.use_fallback:
                logger.warning("GPT-4o-mini found 0 people, trying Perplexity real-time search fallback...")
                people_data = self._fallback_extraction_with_perplexity(
                    team_url, structured_text, html_content, screenshot_path, org_id, org_name
                )

            # Add metadata
            for person in people_data:
                person["source_url"] = team_url
                person["screenshot_path"] = str(screenshot_path) if screenshot_path else None
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

    def _fallback_extraction_with_perplexity(
        self,
        team_url: str,
        structured_text: str | None,
        html_content: str,
        screenshot_path: Path,
        org_id: str,
        org_name: str,
    ) -> list[dict]:
        """
        Fallback extraction using Perplexity's real-time web search when HTML scraping fails.

        Perplexity can search the web in real-time to find current team member information.
        """
        logger.info("🔄 Attempting Perplexity real-time search fallback...")

        prompt = f"""You are helping to find team members at a venture capital firm.

Firm Name: "{org_name}"
Website: {team_url}

Task: Based on your knowledge (LinkedIn, news articles, public profiles, etc.), list the people who work at this VC firm.

For each person, provide:
- name: Full name
- title: Job title/role (e.g., "Partner", "Managing Partner", "Principal", "Analyst")
- profile_url: null (we'll find this later)
- headshot_url: null (we'll find this later)
- evidence_url: URL where you found this person (LinkedIn profile, news article, etc.), or null if unavailable

IMPORTANT:
1. Use your general knowledge about this firm - you don't need to extract from the HTML
2. Include well-known partners, principals, and team members
3. Focus on investment team members (not just support staff)
4. If you don't know anyone at this firm, return []
5. Return ONLY a valid JSON array (no explanations, no suggestions)

Example output:
[
  {{"name": "John Smith", "title": "Managing Partner", "profile_url": null, "headshot_url": null, "evidence_url": "https://linkedin.com/in/johnsmith"}},
  {{"name": "Jane Doe", "title": "Partner", "profile_url": null, "headshot_url": null, "evidence_url": null}}
]

Return ONLY the JSON array (no explanation):"""

        logger.info(f"📤 Perplexity Fallback Prompt for {org_name}:")
        logger.info(f"   Firm: {org_name}")
        logger.info(f"   URL: {team_url}")

        try:
            response = self.llm_fallback.invoke(prompt)
            content = response.content.strip()

            logger.info(f"📥 Perplexity Raw Response ({len(content)} chars): {content[:500]}{'...' if len(content) > 500 else ''}")

            # Clean markdown
            if content.startswith("```"):
                content = re.sub(r"```json\s*|\s*```", "", content).strip()

            people_data = json.loads(content)

            logger.info(f"✅ Perplexity Parsed Response: {len(people_data)} people in array")

            if len(people_data) > 0:
                logger.success(f"✅ Perplexity real-time search found {len(people_data)} people!")
            else:
                logger.warning("Perplexity found 0 people - firm may have no public team information")

            return people_data

        except json.JSONDecodeError as e:
            logger.error(f"Perplexity fallback JSON parse error: {e}")
            logger.error(f"Response was: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Perplexity fallback error: {e}")
            return []

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
            # Determine extraction method and evidence URL
            extraction_method = "openai_gpt4o_mini"
            evidence_url = person_data["source_url"]

            # If Perplexity provided an evidence_url, use it and update method
            if person_data.get("evidence_url"):
                evidence_url = person_data["evidence_url"]
                extraction_method = "perplexity_real_time_search"

            evidence = Evidence(
                person_id=person_id,
                evidence_type="vc_crawler_extraction",
                url=evidence_url,
                screenshot_url=person_data.get("screenshot_path"),
                extracted_data={
                    "name": person_data["name"],
                    "title": person_data.get("title"),
                    "profile_url": profile_url,
                    "headshot_url": headshot_url,
                    "confidence": 0.9,  # High confidence for direct extraction
                },
                extraction_method=extraction_method,
            )
            db.add(evidence)
            logger.debug(f"Saved evidence for: {person_data['name']}")


    def create_agent_run(self, org_id: str, org_name: str, input_params: dict) -> str:
        """Create a new agent run record and return its ID."""
        with get_db() as db:
            run = AgentRun(
                agent_name="vc_crawler",
                status="running",
                input_params={
                    "org_id": org_id,
                    "org_name": org_name,
                    **input_params,
                },
                started_at=datetime.utcnow(),
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return str(run.id)

    def complete_agent_run(
        self, run_id: str, status: str, output_summary: dict, error_message: str | None = None
    ):
        """Update agent run with completion status."""
        with get_db() as db:
            run = db.get(AgentRun, run_id)
            if run:
                run.status = status
                run.completed_at = datetime.utcnow()
                run.output_summary = output_summary
                run.error_message = error_message
                db.commit()

    def crawl_vc(self, org: Organization) -> dict:
        """
        Crawl a single VC organization.

        Returns stats dict with counts.
        """
        # Create agent run record
        run_id = self.create_agent_run(
            org_id=str(org.id),
            org_name=org.name,
            input_params={"website": org.website, "use_fallback": self.use_fallback},
        )

        stats = {
            "org_name": org.name,
            "org_id": str(org.id),
            "run_id": run_id,
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
                self.complete_agent_run(run_id, "failed", stats, "No website found")
                return stats

            with sync_playwright() as p:
                # Launch browser with Railway-compatible settings
                # Disable GPU, sandbox, and shared memory to avoid crashes in containerized environments
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-gpu',
                        '--disable-dev-shm-usage',  # Use /tmp instead of /dev/shm
                        '--disable-setuid-sandbox',
                        '--no-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )

                try:
                    # Find team page
                    team_url = self.find_team_page(browser, website)

                    # If no team page found, try Perplexity fallback directly
                    if not team_url and self.use_fallback:
                        logger.warning(f"No team page found for {org.name}, trying Perplexity fallback...")
                        people_data = self._fallback_extraction_with_perplexity(
                            team_url=website,  # Use main website as reference
                            structured_text=None,
                            html_content="",
                            screenshot_path=None,
                            org_id=str(org.id),
                            org_name=org.name
                        )
                        stats["people_found"] = len(people_data)

                        # Save to database
                        for person_data in people_data:
                            # Add metadata since we didn't go through extract_people_from_page
                            person_data["source_url"] = website
                            person_data["screenshot_path"] = None
                            person_data["org_id"] = str(org.id)

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
                            f"{stats['roles_created']} roles (via Perplexity fallback)"
                        )

                        # Mark as completed successfully
                        self.complete_agent_run(run_id, "completed", stats)
                        return stats
                    elif not team_url:
                        stats["error"] = "Team page not found"
                        self.complete_agent_run(run_id, "failed", stats, "Team page not found")
                        return stats

                    # Extract people
                    people_data = self.extract_people_from_page(browser, team_url, str(org.id), org.name)
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

                    # Mark as completed successfully
                    self.complete_agent_run(run_id, "completed", stats)

                finally:
                    browser.close()

        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Error crawling {org.name}: {e}")
            self.complete_agent_run(run_id, "failed", stats, str(e))

        return stats

    def crawl_all_vcs(self, limit: int | None = None) -> dict:
        """
        Crawl all VCs in database.

        Args:
            limit: Maximum number of VCs to crawl (None = all)

        Returns:
            Overall statistics
        """
        # Get all VCs and extract data we need before session closes
        with get_db() as db:
            stmt = select(Organization).where(Organization.kind == "vc")
            if limit:
                stmt = stmt.limit(limit)
            vcs_data = [
                {"id": vc.id, "name": vc.name, "website": vc.website}
                for vc in db.execute(stmt).scalars().all()
            ]

        logger.info(f"Found {len(vcs_data)} VCs to crawl")

        overall_stats = {
            "total_vcs": len(vcs_data),
            "vcs_processed": 0,
            "people_created": 0,
            "people_updated": 0,
            "people_skipped": 0,
            "total_roles": 0,
            "errors": [],
        }

        for i, vc_data in enumerate(vcs_data, 1):
            logger.info(f"\n[{i}/{len(vcs_data)}] Crawling: {vc_data['name']}")

            # Fetch fresh vc object for each crawl
            with get_db() as db:
                vc = db.get(Organization, vc_data["id"])
                stats = self.crawl_vc(vc)

            overall_stats["vcs_processed"] += 1
            overall_stats["people_created"] += stats["people_created"]
            overall_stats["people_updated"] += stats["people_updated"]
            overall_stats["people_skipped"] += stats["people_skipped"]
            overall_stats["total_roles"] += stats["roles_created"]

            if stats["error"]:
                overall_stats["errors"].append(f"{vc_data['name']}: {stats['error']}")

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
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable Perplexity fallback (use only GPT-4o-mini)",
    )

    args = parser.parse_args()

    # Override recrawl setting if force-refresh is set
    if args.force_refresh:
        logger.info("🔄 Force refresh mode enabled - will update all people regardless of age")
        settings.recrawl_after_days = 0

    logger.info("🕷️  Starting VC Crawler Agent...")

    crawler = VCCrawler(use_fallback=not args.no_fallback)

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
