#!/usr/bin/env python3
"""
Social Enricher Agent - Find social media handles for people.

Strategy:
1. Use Perplexity (real-time web search) to find Twitter/X handle
2. Search Farcaster using Neynar API (by Twitter handle or name)
3. Infer Telegram handle from Farcaster/Twitter if identical
4. Update people.socials with confidence scores
"""

import json
from datetime import datetime

import requests
from langchain_openai import ChatOpenAI
from loguru import logger
from sqlalchemy import select

from src.config import settings
from src.db.connection import get_db
from src.db.models import Person


class SocialEnricher:
    """Enriches people with social media handles."""

    def __init__(self):
        """Initialize the enricher with API clients."""
        self.neynar_api_key = settings.neynar_api_key

        # Use Perplexity for Twitter handle discovery (has real-time web search)
        self.llm = ChatOpenAI(
            model="sonar",
            temperature=0.3,
            api_key=settings.perplexity_api_key,
            base_url="https://api.perplexity.ai",
        )

    def find_twitter_handle(self, person: Person, org_name: str = "") -> dict | None:
        """
        Use Perplexity (real-time web search) to find Twitter/X handle.

        Returns dict with: handle, confidence, source
        """
        # Get profile URL from socials JSONB field
        profile_url = person.socials.get("profile_url") if person.socials else None

        prompt = f"""Find the Twitter/X handle for this person:

Name: {person.full_name}
Company: {org_name}
{f"Profile: {profile_url}" if profile_url else ""}
{f"Email: {person.email}" if person.email else ""}

Search the web and return ONLY a JSON object with:
{{
    "handle": "twitter_username_only (WITHOUT @, no spaces, just the handle like 'elonmusk')",
    "confidence": 0.0-1.0,
    "source": "URL where you found it"
}}

IMPORTANT: The handle must be ONLY the username (alphanumeric + underscores), NOT a full name or URL.
Examples: "sama", "vitalikbuterin", "richardmuirhead"

If not found or uncertain, return:
{{"handle": null, "confidence": 0.0, "source": null}}

Return ONLY valid JSON, no explanations."""

        try:
            logger.debug(f"Asking Perplexity to find Twitter handle for {person.full_name}")
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            logger.debug(f"Perplexity raw response: {content}")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            logger.debug(f"Parsed data: {data}")

            if data.get("handle") and data.get("confidence", 0) >= 0.6:
                logger.info(
                    f"✓ Found Twitter: {person.full_name} → @{data['handle']} "
                    f"(confidence: {data['confidence']:.2f})"
                )
                return data

            logger.debug(
                f"No confident Twitter match for {person.full_name} "
                f"(confidence: {data.get('confidence', 0):.2f})"
            )
            return None

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Perplexity Twitter response: {e}")
            logger.debug(f"Raw response: {content}")
            return None
        except Exception as e:
            logger.error(f"Error finding Twitter handle for {person.full_name}: {e}")
            return None

    def search_farcaster(
        self, person: Person, org_name: str = "", twitter_handle: str = None
    ) -> dict | None:
        """
        Search for person on Farcaster using Neynar API.
        Can also search by Twitter handle if provided.

        Returns dict with: username, fid, display_name, bio, verified, confidence
        """
        if not self.neynar_api_key:
            logger.warning("No Neynar API key configured - skipping Farcaster search")
            return None

        # Strategy 1: If we have Twitter handle, search by that first
        if twitter_handle:
            logger.debug(f"Searching Farcaster by Twitter handle: @{twitter_handle}")
            try:
                response = requests.get(
                    "https://api.neynar.com/v2/farcaster/user/search",
                    headers={"api_key": self.neynar_api_key, "accept": "application/json"},
                    params={"q": twitter_handle, "limit": 5},
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("result") and data["result"].get("users"):
                    # Look for exact username match
                    for user in data["result"]["users"]:
                        if user.get("username", "").lower() == twitter_handle.lower():
                            logger.info(
                                f"✓ Found Farcaster via Twitter handle: @{twitter_handle} "
                                f"(fid: {user.get('fid')})"
                            )
                            return {
                                "username": user.get("username"),
                                "fid": user.get("fid"),
                                "display_name": user.get("display_name"),
                                "bio": user.get("profile", {}).get("bio", {}).get("text"),
                                "verified": user.get("verifications", []),
                                "confidence": 0.8,  # High confidence from Twitter match
                            }
            except requests.RequestException as e:
                logger.debug(f"Twitter handle search failed: {e}")

        # Strategy 2: Search by name + context
        # Extract email domain if available
        email_domain = None
        if person.email:
            email_domain = person.email.split("@")[1] if "@" in person.email else None

        # Build search query - Neynar limits to 20 chars max
        search_query = person.full_name[:20]  # Truncate to 20 chars max

        logger.debug(f"Searching Farcaster by name: {search_query}")

        try:
            # Neynar API: Search for users
            # Docs: https://docs.neynar.com/reference/search-user
            response = requests.get(
                "https://api.neynar.com/v2/farcaster/user/search",
                headers={"api_key": self.neynar_api_key, "accept": "application/json"},
                params={"q": search_query, "limit": 5},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("result") or not data["result"].get("users"):
                logger.debug(f"No Farcaster users found for {person.full_name}")
                return None

            # Find best match
            users = data["result"]["users"]
            best_match = None
            highest_confidence = 0.0

            for user in users:
                confidence = self._calculate_farcaster_confidence(
                    person, user, org_name, email_domain
                )

                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_match = {
                        "username": user.get("username"),
                        "fid": user.get("fid"),
                        "display_name": user.get("display_name"),
                        "bio": user.get("profile", {}).get("bio", {}).get("text"),
                        "verified": user.get("verifications", []),
                        "confidence": confidence,
                    }

            if best_match and highest_confidence >= 0.5:
                logger.info(
                    f"✓ Found Farcaster: {person.full_name} → @{best_match['username']} "
                    f"(confidence: {highest_confidence:.2f})"
                )
                return best_match

            logger.debug(
                f"No confident Farcaster match for {person.full_name} "
                f"(best: {highest_confidence:.2f})"
            )
            return None

        except requests.RequestException as e:
            logger.error(f"Farcaster API error for {person.full_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.debug(f"Response status: {e.response.status_code}")
                logger.debug(f"Response body: {e.response.text[:500]}")
            return None

    def _calculate_farcaster_confidence(
        self,
        person: Person,
        fc_user: dict,
        org_name: str = "",
        email_domain: str = None,
    ) -> float:
        """Calculate confidence score for Farcaster match."""
        confidence = 0.0

        # Base: name similarity (simple check)
        fc_name = fc_user.get("display_name", "").lower()
        person_name = person.full_name.lower()

        if fc_name == person_name:
            confidence += 0.5
        elif person_name in fc_name or fc_name in person_name:
            confidence += 0.3

        # Verified email domain
        if email_domain:
            verifications = fc_user.get("verifications", [])
            for addr in verifications:
                if email_domain in addr.lower():
                    confidence += 0.4
                    break

        # Company/org in bio
        bio = fc_user.get("profile", {}).get("bio", {}).get("text", "").lower()
        if org_name and org_name.lower() in bio:
            confidence += 0.2

        return min(confidence, 1.0)

    def infer_telegram(
        self, farcaster_handle: str = None, twitter_handle: str = None
    ) -> tuple[str, float] | None:
        """
        Infer Telegram handle from other socials if identical.

        Returns: (telegram_handle, confidence) or None
        """
        # If handles are identical, likely same on Telegram
        if farcaster_handle and twitter_handle:
            if farcaster_handle.lower() == twitter_handle.lower():
                logger.info(
                    f"✓ Inferred Telegram from handle parity: @{farcaster_handle}"
                )
                return (farcaster_handle, 0.6)

        # Single handle - lower confidence
        handle = farcaster_handle or twitter_handle
        if handle:
            logger.debug(f"Weak Telegram inference from @{handle} (confidence: 0.5)")
            return (handle, 0.5)

        return None

    def enrich_person(self, person: Person, org_name: str = "") -> dict:
        """
        Enrich a single person with social handles.

        Returns dict with enrichment results.
        """
        result = {
            "person_id": str(person.id),
            "person_name": person.full_name,
            "farcaster": None,
            "twitter": None,
            "telegram": None,
            "updated": False,
        }

        # Step 1: Find Twitter handle using Perplexity (real-time web search)
        tw_result = self.find_twitter_handle(person, org_name)
        if tw_result:
            result["twitter"] = tw_result

        # Step 2: Search Farcaster (can use Twitter handle for better matching)
        twitter_handle = tw_result.get("handle") if tw_result else None
        fc_result = self.search_farcaster(person, org_name, twitter_handle)
        if fc_result:
            result["farcaster"] = fc_result

        # Step 3: Infer Telegram from handle parity
        fc_handle = fc_result.get("username") if fc_result else None
        tg_result = self.infer_telegram(fc_handle, twitter_handle)

        if tg_result:
            tg_handle, tg_confidence = tg_result
            result["telegram"] = {"handle": tg_handle, "confidence": tg_confidence}

        # Update database if we found anything
        if fc_result or result["twitter"] or result["telegram"]:
            self._update_person_socials(person, result)
            result["updated"] = True

        return result

    def _update_person_socials(self, person: Person, enrichment: dict):
        """Update person's socials in database."""
        with get_db() as db:
            # Refresh person object
            db_person = db.get(Person, person.id)

            # Update socials
            if enrichment["farcaster"]:
                fc = enrichment["farcaster"]
                db_person.socials["farcaster"] = fc["username"]
                db_person.socials["farcaster_fid"] = fc["fid"]
                db_person.socials["farcaster_confidence"] = fc["confidence"]

            if enrichment["twitter"]:
                tw = enrichment["twitter"]
                db_person.socials["twitter"] = tw["handle"]
                db_person.socials["twitter_confidence"] = tw["confidence"]

            if enrichment["telegram"]:
                tg = enrichment["telegram"]
                db_person.telegram_handle = tg["handle"]
                db_person.telegram_confidence = tg["confidence"]

            # Update enrichment history
            if not db_person.enrichment_history:
                db_person.enrichment_history = []

            db_person.enrichment_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "social_enricher",
                    "farcaster": enrichment["farcaster"] is not None,
                    "twitter": enrichment["twitter"] is not None,
                    "telegram": enrichment["telegram"] is not None,
                }
            )

            db.commit()
            logger.info(f"✓ Updated socials for {person.full_name}")

    def enrich_all_people(
        self, limit: int = None, min_confidence: float = 0.6
    ) -> dict:
        """
        Enrich all people lacking social handles.

        Args:
            limit: Max number of people to process
            min_confidence: Minimum confidence threshold

        Returns:
            Statistics dict
        """
        with get_db() as db:
            # Find people without Farcaster handle
            stmt = select(Person).where(
                ~Person.socials.has_key("farcaster")  # type: ignore
            )
            if limit:
                stmt = stmt.limit(limit)

            people = db.execute(stmt).scalars().all()

        logger.info(f"Found {len(people)} people to enrich")

        stats = {
            "total_people": len(people),
            "enriched": 0,
            "farcaster_found": 0,
            "twitter_found": 0,
            "telegram_inferred": 0,
        }

        for i, person in enumerate(people, 1):
            logger.info(f"\n[{i}/{len(people)}] Enriching: {person.full_name}")

            # Get org name from roles
            org_name = ""
            with get_db() as db:
                db_person = db.get(Person, person.id)
                if db_person.roles:
                    org_name = db_person.roles[0].organization.name

            result = self.enrich_person(person, org_name)

            if result["updated"]:
                stats["enriched"] += 1
            if result["farcaster"]:
                stats["farcaster_found"] += 1
            if result["twitter"]:
                stats["twitter_found"] += 1
            if result["telegram"]:
                stats["telegram_inferred"] += 1

        return stats


def main():
    """Main entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich people with social handles")
    parser.add_argument("--limit", type=int, help="Limit number of people to enrich")
    parser.add_argument(
        "--person-name", type=str, help="Enrich specific person by name"
    )

    args = parser.parse_args()

    logger.info("🔍 Starting Social Enricher Agent...")

    enricher = SocialEnricher()

    if args.person_name:
        # Enrich specific person
        with get_db() as db:
            stmt = select(Person).where(Person.full_name.ilike(f"%{args.person_name}%"))
            person = db.execute(stmt).scalar_one_or_none()

            if not person:
                logger.error(f"Person not found: {args.person_name}")
                return

            # Get org name
            org_name = ""
            if person.roles:
                org_name = person.roles[0].organization.name

            result = enricher.enrich_person(person, org_name)
            logger.info(f"\n📊 Result: {json.dumps(result, indent=2)}")
    else:
        # Enrich all people
        stats = enricher.enrich_all_people(limit=args.limit)

        logger.info("\n" + "=" * 60)
        logger.info("📊 Enrichment Summary:")
        logger.info(f"   People processed: {stats['total_people']}")
        logger.info(f"   People enriched: {stats['enriched']}")
        logger.info(f"   Farcaster found: {stats['farcaster_found']}")
        logger.info(f"   Twitter found: {stats['twitter_found']}")
        logger.info(f"   Telegram inferred: {stats['telegram_inferred']}")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
