# Agent: Social Enricher


**Input:** People lacking socials/telegram
**Output:** Updated `people.socials`, `telegram_handle`, `confidence`


## Farcaster
- Query by name + domain/email guess; prefer verified accounts; capture fid and username.


## X/Twitter (optional if API key present)
- Query by name + org; require recent activity OR company match in bio.


## Telegram (inference only)
- If a profile explicitly lists Telegram → use it.
- Else, if Farcaster or X handle is present and **exactly identical** (case‑insensitive) to a known Telegram handle pattern, set `telegram_handle` with `confidence` 0.6 (explicit listing → 0.9).


## Confidence scoring (suggestion)
- 0.9 explicit link; 0.75 name+company match + recent activity; 0.6 handle parity only.