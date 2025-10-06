# Agent: VC Crawler


**Input:** VC `orgs.website`
**Output:** `people`, `roles_employment`, `evidence`


## Strategy
- Discover team/about URLs by sitemap, nav anchors, regex (team|people|about|leadership).
- Use Playwright; wait for network idle; extract cards/links; capture page screenshot.


## Selectors (try in order)
- Semantic: elements with role=link and innerText matches /(team|people|partners)/i
- CSS fallbacks: `.team*, .people*, a[href*="team"], a[href*="people"], a[href*="leadership"]`
- Card patterns: `[class*="team" i] .card`, `img + h3`, `figure + h3`, microdata `itemprop=employee`.


## Output fields per person
- `name`, `title`, `profile_url`, `org_id`, `source.url`, `selector`, optional `headshot_url`.


## Evidence
- Store `url`, `selector`, `snapshot_url` (if using a screenshot store), extracted JSON chunk.