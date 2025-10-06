"""Utility functions for data normalization and hashing."""

import hashlib
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import validators


def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize a URL for consistency.

    - Converts to lowercase
    - Removes trailing slashes
    - Removes www. prefix
    - Removes query params and fragments
    """
    if not url:
        return None

    url = url.strip().lower()

    # Parse URL
    parsed = urlparse(url)

    # Remove www. prefix
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Reconstruct without query/fragment
    normalized = f"{parsed.scheme}://{netloc}{parsed.path}".rstrip("/")

    return normalized


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for deduplication.

    - Lowercase
    - Remove special characters
    - Remove common suffixes (Inc, LLC, etc.)
    """
    if not name:
        return ""

    # Lowercase
    name = name.lower().strip()

    # Remove common legal suffixes
    suffixes = [
        r"\s+(inc\.?|llc\.?|ltd\.?|limited|corp\.?|corporation|ventures?|capital|partners?)$",
    ]
    for suffix in suffixes:
        name = re.sub(suffix, "", name, flags=re.IGNORECASE)

    # Remove special characters (keep letters, numbers, spaces)
    name = re.sub(r"[^a-z0-9\s]", "", name)

    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()

    return name


def generate_org_uniq_key(name: str, website: Optional[str] = None) -> str:
    """
    Generate unique key for organization deduplication.

    Format: sha256(normalized_name + normalized_website)
    """
    normalized_name = normalize_company_name(name)
    normalized_website = normalize_url(website) if website else ""

    combined = f"{normalized_name}|{normalized_website}"
    return hashlib.sha256(combined.encode()).hexdigest()


def generate_deal_uniq_hash(
    org_name: str,
    announced_on: datetime,
    round_type: Optional[str],
    amount_usd: Optional[float],
) -> str:
    """
    Generate unique hash for deal idempotency.

    Format: sha256(normalized_name|date|round|amount)
    """
    normalized_name = normalize_company_name(org_name)
    date_str = announced_on.strftime("%Y-%m-%d") if announced_on else ""
    round_str = (round_type or "").lower().strip()
    amount_str = f"{amount_usd:.2f}" if amount_usd else "0"

    combined = f"{normalized_name}|{date_str}|{round_str}|{amount_str}"
    return hashlib.sha256(combined.encode()).hexdigest()


def generate_person_uniq_key(full_name: str, email: Optional[str] = None) -> str:
    """
    Generate unique key for person deduplication.

    Format: sha256(normalized_name + email)
    """
    normalized_name = full_name.lower().strip()
    normalized_email = email.lower().strip() if email else ""

    combined = f"{normalized_name}|{normalized_email}"
    return hashlib.sha256(combined.encode()).hexdigest()


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return None


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    return bool(validators.url(url))


def is_valid_email(email: str) -> bool:
    """Check if email is valid."""
    return bool(validators.email(email))


def normalize_currency_to_eur(
    amount: float,
    currency: str,
    exchange_rates: Optional[dict[str, float]] = None,
) -> float:
    """
    Convert currency to EUR.

    Args:
        amount: Amount in original currency
        currency: Currency code (USD, ETH, etc.)
        exchange_rates: Optional dict of currency -> EUR rates

    Returns:
        Amount in EUR
    """
    if not exchange_rates:
        # Default rates (should be fetched from API in production)
        exchange_rates = {
            "USD": 0.92,  # 1 USD = 0.92 EUR
            "EUR": 1.0,
            "GBP": 1.17,
            "ETH": 2800.0,  # Approximate, should be dynamic
            "BTC": 58000.0,  # Approximate, should be dynamic
        }

    currency = currency.upper()
    rate = exchange_rates.get(currency, 1.0)

    return amount * rate


def clean_text(text: str) -> str:
    """
    Clean text content.

    - Remove extra whitespace
    - Remove special characters
    - Normalize line breaks
    """
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    return text.strip()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def parse_linkedin_url(url: str) -> Optional[str]:
    """
    Extract LinkedIn username from URL.

    Examples:
        https://linkedin.com/in/username -> username
        https://www.linkedin.com/in/username/ -> username
    """
    if not url:
        return None

    match = re.search(r"linkedin\.com/in/([^/?]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def parse_twitter_handle(text: str) -> Optional[str]:
    """
    Extract Twitter handle from text.

    Examples:
        @username -> username
        twitter.com/username -> username
        https://x.com/username -> username
    """
    if not text:
        return None

    # Handle URL format
    url_match = re.search(
        r"(?:twitter\.com|x\.com)/([^/?]+)", text, re.IGNORECASE)
    if url_match:
        return url_match.group(1)

    # Handle @username format
    handle_match = re.search(r"@([a-zA-Z0-9_]+)", text)
    if handle_match:
        return handle_match.group(1)

    return None
