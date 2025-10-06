**Inputs**
- person: {name, title}
- org: {name, focus, latest_deal?}
- ties: {shared_follow?, mutual_startup?, farcaster_handle?, telegram_handle?}
- value_prop: short string you provide


**Template**
Hi {name} — noticed your work as {title} at {org}. {if latest_deal}Congrats on {latest_deal.round} with {latest_deal.org}{/if}; aligns with {org.focus}.


I’m {your_name} building {value_prop}. Given our {tie_snippet_if_any}, thought a quick intro could be useful. Open to a short chat? Happy to send a 3‑bullet overview.