"""
VC Agents Admin Dashboard

Simple Streamlit UI for managing VCs, people, and triggering agents.
"""

from datetime import datetime

import streamlit as st
from sqlalchemy import desc, func

from src.db.connection import get_db
from src.db.models import AgentRun, Deal, Evidence, Organization, Person, RoleEmployment

# Page config
st.set_page_config(
    page_title="VC Agents Admin",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    if 'running_agents' not in st.session_state:
        st.session_state.running_agents = set()


def get_stats():
    """Get database statistics."""
    with get_db() as db:
        stats = {
            'total_orgs': db.query(func.count(Organization.id)).filter(
                Organization.kind == 'vc'
            ).scalar() or 0,
            'orgs_with_website': db.query(func.count(Organization.id)).filter(
                Organization.kind == 'vc',
                Organization.website.isnot(None)
            ).scalar() or 0,
            'total_people': db.query(func.count(Person.id)).scalar() or 0,
            'people_with_twitter': db.query(func.count(Person.id)).filter(
                Person.socials['twitter'].astext.isnot(None)
            ).scalar() or 0,
            'people_with_farcaster': db.query(func.count(Person.id)).filter(
                Person.socials['farcaster'].astext.isnot(None)
            ).scalar() or 0,
            'people_with_telegram': db.query(func.count(Person.id)).filter(
                Person.telegram_handle.isnot(None)
            ).scalar() or 0,
            'recent_agent_runs': db.query(func.count(AgentRun.id)).filter(
                AgentRun.started_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ).scalar() or 0,
        }
    return stats


def show_dashboard():
    """Show main dashboard with statistics."""
    st.markdown('<div class="main-header">🚀 VC Agents Dashboard</div>', unsafe_allow_html=True)

    # Get stats
    stats = get_stats()

    # Display stats in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total VCs",
            stats['total_orgs'],
            f"{stats['orgs_with_website']} with websites"
        )

    with col2:
        st.metric(
            "Total People",
            stats['total_people'],
            f"{stats['people_with_twitter']} with X/Twitter"
        )

    with col3:
        enriched = stats['people_with_twitter'] + stats['people_with_farcaster'] + stats['people_with_telegram']
        st.metric(
            "Social Enrichment",
            f"{enriched} profiles",
            f"{stats['people_with_telegram']} with Telegram"
        )

    with col4:
        st.metric(
            "Agent Runs Today",
            stats['recent_agent_runs']
        )

    st.divider()

    # Quick actions
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔍 Find All VC Websites", use_container_width=True):
            run_website_finder()

    with col2:
        if st.button("🕷️ Crawl All VCs", use_container_width=True):
            run_vc_crawler()

    with col3:
        if st.button("💼 Enrich All People", use_container_width=True):
            run_social_enricher()


def show_orgs():
    """Show organizations table with actions."""
    st.header("🏢 Organizations (VCs)")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("Search by name", placeholder="Enter VC name...")
    with col2:
        has_website = st.selectbox("Website status", ["All", "With website", "Without website"])
    with col3:
        sort_by = st.selectbox("Sort by", ["Name", "Created date", "Updated date"])

    # Get organizations
    with get_db() as db:
        query = db.query(Organization).filter(Organization.kind == 'vc')

        if search:
            query = query.filter(Organization.name.ilike(f'%{search}%'))

        if has_website == "With website":
            query = query.filter(Organization.website.isnot(None))
        elif has_website == "Without website":
            query = query.filter(Organization.website.is_(None))

        if sort_by == "Name":
            query = query.order_by(Organization.name)
        elif sort_by == "Created date":
            query = query.order_by(desc(Organization.created_at))
        else:
            query = query.order_by(desc(Organization.updated_at))

        orgs_data = query.limit(100).all()

        # Convert to dictionaries to avoid detached instance errors
        orgs = []
        for org in orgs_data:
            # Get people count within the same session
            people_count = db.query(func.count(RoleEmployment.person_id)).filter(
                RoleEmployment.org_id == org.id
            ).scalar() or 0

            # Get most recent screenshot from Evidence
            latest_screenshot = db.query(Evidence.screenshot_url).filter(
                Evidence.org_id == org.id,
                Evidence.screenshot_url.isnot(None)
            ).order_by(desc(Evidence.created_at)).first()

            orgs.append({
                'id': str(org.id),
                'name': org.name,
                'website': org.website,
                'kind': org.kind,
                'created_at': org.created_at,
                'people_count': people_count,
                'screenshot': latest_screenshot[0] if latest_screenshot else None
            })

    if not orgs:
        st.info("No organizations found. Load some deals first: `make load-deals`")
        return

    # Display count
    st.caption(f"Showing {len(orgs)} organizations")

    # Display organizations
    for org in orgs:
        # Build status indicator
        status = ""
        if not org['website']:
            status = " ⚠️ No website"
        elif org['people_count'] == 0:
            status = " 👥 No team members"
        else:
            status = " ✅"

        with st.expander(f"{org['name']}{status}"):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**Name:** {org['name']}")
                st.write(f"**Website:** {org['website'] or 'Not found'}")
                st.write(f"**Kind:** {org['kind']}")
                st.write(f"**Created:** {org['created_at'].strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Team members:** {org['people_count']}")

                # Show screenshot if available
                if org['screenshot']:
                    st.write("**Latest Screenshot:**")
                    try:
                        st.image(org['screenshot'], caption="Team page screenshot", use_container_width=True)
                    except Exception as e:
                        st.caption(f"Screenshot path: {org['screenshot']}")
                        st.caption(f"(Could not load image: {e})")

            with col2:
                if st.button("🔍 Find Website", key=f"find_{org['id']}"):
                    run_website_finder(org['name'])

                if org['website'] and st.button("🕷️ Crawl Team", key=f"crawl_{org['id']}"):
                    run_vc_crawler(org['name'])

                if st.button("🗑️ Delete", key=f"del_{org['id']}"):
                    if st.session_state.get(f"confirm_del_{org['id']}"):
                        with get_db() as db:
                            db.query(Organization).filter(
                                Organization.id == org['id']
                            ).delete()
                            db.commit()
                        st.success("Deleted!")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_del_{org['id']}"] = True
                        st.warning("Click again to confirm")


def show_people():
    """Show people table with actions."""
    st.header("👥 People")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("Search by name", placeholder="Enter person name...")
    with col2:
        enrichment = st.selectbox("Enrichment status", [
            "All",
            "With X/Twitter",
            "With Farcaster",
            "With Telegram",
            "Not enriched"
        ])
    with col3:
        sort_by = st.selectbox("Sort by", ["Name", "Updated date", "Confidence"])

    # Get people
    with get_db() as db:
        query = db.query(Person)

        if search:
            query = query.filter(Person.full_name.ilike(f'%{search}%'))

        if enrichment == "With X/Twitter":
            query = query.filter(Person.socials['twitter'].astext.isnot(None))
        elif enrichment == "With Farcaster":
            query = query.filter(Person.socials['farcaster'].astext.isnot(None))
        elif enrichment == "With Telegram":
            query = query.filter(Person.telegram_handle.isnot(None))
        elif enrichment == "Not enriched":
            query = query.filter(
                Person.socials['twitter'].astext.is_(None),
                Person.socials['farcaster'].astext.is_(None),
                Person.telegram_handle.is_(None)
            )

        if sort_by == "Name":
            query = query.order_by(Person.full_name)
        elif sort_by == "Updated date":
            query = query.order_by(desc(Person.updated_at))
        else:
            query = query.order_by(desc(Person.telegram_confidence))

        people_data = query.limit(100).all()

        # Convert to dictionaries to avoid detached instance errors
        people = []
        for person in people_data:
            # Get role within the same session
            role = db.query(RoleEmployment, Organization).join(
                Organization, RoleEmployment.org_id == Organization.id
            ).filter(RoleEmployment.person_id == person.id).first()

            # Get most recent screenshot from Evidence
            latest_screenshot = db.query(Evidence.screenshot_url).filter(
                Evidence.person_id == person.id,
                Evidence.screenshot_url.isnot(None)
            ).order_by(desc(Evidence.created_at)).first()

            people.append({
                'id': str(person.id),
                'full_name': person.full_name,
                'socials': person.socials or {},
                'telegram_handle': person.telegram_handle,
                'telegram_confidence': person.telegram_confidence,
                'updated_at': person.updated_at,
                'org_name': role.Organization.name if role else None,
                'title': role.RoleEmployment.title if role else None,
                'screenshot': latest_screenshot[0] if latest_screenshot else None
            })

    if not people:
        st.info("No people found. Run the VC crawler first: `make run-crawler`")
        return

    # Group people by organization
    from collections import defaultdict
    people_by_org = defaultdict(list)

    for person in people:
        org_name = person['org_name'] or "Unknown Organization"
        people_by_org[org_name].append(person)

    # Sort organizations alphabetically
    sorted_orgs = sorted(people_by_org.keys())

    st.caption(f"Showing {len(people)} people across {len(people_by_org)} organizations")

    # Display people grouped by organization
    for org_name in sorted_orgs:
        org_people = people_by_org[org_name]

        # Organization header with count
        with st.expander(f"🏢 {org_name} ({len(org_people)} {'person' if len(org_people) == 1 else 'people'})", expanded=False):
            for person in org_people:
                socials = person['socials'] if isinstance(person['socials'], dict) else {}

                # Handle both old format (nested dict) and new format (flat keys)
                # Twitter
                if isinstance(socials.get('twitter'), dict):
                    twitter_username = socials['twitter'].get('username')
                    twitter_confidence = socials['twitter'].get('confidence', 0)
                else:
                    twitter_username = socials.get('twitter')
                    twitter_confidence = socials.get('twitter_confidence', 0)

                # Farcaster
                if isinstance(socials.get('farcaster'), dict):
                    farcaster_username = socials['farcaster'].get('username')
                    farcaster_fid = socials['farcaster'].get('fid')
                    farcaster_confidence = socials['farcaster'].get('confidence', 0)
                else:
                    farcaster_username = socials.get('farcaster')
                    farcaster_fid = socials.get('farcaster_fid')
                    farcaster_confidence = socials.get('farcaster_confidence', 0)

                status_icons = []
                if twitter_username:
                    status_icons.append("🐦")
                if farcaster_username:
                    status_icons.append("🟣")
                if person['telegram_handle']:
                    status_icons.append("✈️")

                # Build display name - simpler since we're already grouped by org
                display_name = person['full_name']
                if person['title']:
                    display_name = f"{person['full_name']} • {person['title']}"

                with st.expander(f"{display_name} {' '.join(status_icons)}"):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**Name:** {person['full_name']}")

                        # Title (org already shown in parent expander)
                        if person['title']:
                            st.write(f"**Title:** {person['title']}")

                        # Social profiles section
                        st.write("**Social Profiles:**")

                        # Twitter/X
                        if twitter_username:
                            st.write(f"  🐦 X (Twitter): [@{twitter_username}](https://x.com/{twitter_username}) (confidence: {twitter_confidence:.2f})")
                        else:
                            st.write("  🐦 X (Twitter): Not found")

                        # Farcaster
                        if farcaster_username:
                            fid_display = f" (FID: {farcaster_fid})" if farcaster_fid else ""
                            st.write(f"  🟣 Farcaster: [@{farcaster_username}](https://farcaster.xyz/{farcaster_username}){fid_display} (confidence: {farcaster_confidence:.2f})")
                        else:
                            st.write("  🟣 Farcaster: Not found")

                        # Telegram - editable
                        telegram = st.text_input(
                            "✈️ Telegram handle",
                            value=person['telegram_handle'] or "",
                            key=f"telegram_{person['id']}",
                            placeholder="@username"
                        )
                        if telegram != (person['telegram_handle'] or ""):
                            if st.button("Save Telegram", key=f"save_telegram_{person['id']}"):
                                with get_db() as db:
                                    db.query(Person).filter(
                                        Person.id == person['id']
                                    ).update({Person.telegram_handle: telegram or None})
                                    db.commit()
                                st.success("Updated!")
                                st.rerun()

                        # Show all other socials if any
                        known_keys = {'twitter', 'twitter_confidence', 'farcaster', 'farcaster_fid', 'farcaster_confidence'}
                        other_socials = {k: v for k, v in socials.items() if k not in known_keys}
                        if other_socials:
                            st.write("**Other Socials:**")
                            for platform, data in other_socials.items():
                                if isinstance(data, dict):
                                    username = data.get('username', data.get('handle', 'N/A'))
                                    confidence = data.get('confidence', 0)
                                    st.write(f"  • {platform.title()}: {username} (confidence: {confidence:.2f})")
                                else:
                                    st.write(f"  • {platform.title()}: {data}")

                        st.write(f"**Telegram Confidence:** {person['telegram_confidence'] or 0:.2f}")
                        st.write(f"**Updated:** {person['updated_at'].strftime('%Y-%m-%d %H:%M')}")

                        # Show screenshot if available
                        if person['screenshot']:
                            st.write("**Latest Screenshot:**")
                            try:
                                st.image(person['screenshot'], caption="Team page screenshot", use_container_width=True)
                            except Exception as e:
                                st.caption(f"Screenshot path: {person['screenshot']}")
                                st.caption(f"(Could not load image: {e})")

                    with col2:
                        if st.button("💼 Enrich", key=f"enrich_{person['id']}"):
                            run_social_enricher(person['full_name'])

                        if st.button("🗑️ Delete", key=f"del_person_{person['id']}"):
                            if st.session_state.get(f"confirm_del_person_{person['id']}"):
                                with get_db() as db:
                                    db.query(Person).filter(
                                        Person.id == person['id']
                                    ).delete()
                                    db.commit()
                                st.success("Deleted!")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_del_person_{person['id']}"] = True
                                st.warning("Click again to confirm")


def show_agent_runs():
    """Show agent execution history."""
    st.header("🤖 Agent Runs")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        agent_type = st.selectbox("Agent type", [
            "All",
            "website_finder",
            "vc_crawler",
            "social_enricher"
        ])
    with col2:
        status = st.selectbox("Status", ["All", "completed", "failed", "running"])

    # Get agent runs
    with get_db() as db:
        query = db.query(AgentRun).order_by(desc(AgentRun.started_at))

        if agent_type != "All":
            query = query.filter(AgentRun.agent_name == agent_type)

        if status != "All":
            query = query.filter(AgentRun.status == status)

        runs_data = query.limit(50).all()

        # Convert to dictionaries to avoid detached instance errors
        runs = []
        for run in runs_data:
            runs.append({
                'agent_name': run.agent_name,
                'status': run.status,
                'started_at': run.started_at,
                'completed_at': run.completed_at,
                'input_params': run.input_params,
                'output_summary': run.output_summary,
                'error_message': run.error_message
            })

    if not runs:
        st.info("No agent runs found yet.")
        return

    st.caption(f"Showing {len(runs)} recent runs")

    # Display runs
    for run in runs:
        status_emoji = {
            'completed': '✅',
            'failed': '❌',
            'running': '⏳'
        }.get(run['status'], '❓')

        with st.expander(
            f"{status_emoji} {run['agent_name']} - {run['started_at'].strftime('%Y-%m-%d %H:%M:%S')}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Agent:** {run['agent_name']}")
                st.write(f"**Status:** {run['status']}")
                st.write(f"**Started:** {run['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                if run['completed_at']:
                    duration = (run['completed_at'] - run['started_at']).total_seconds()
                    st.write(f"**Duration:** {duration:.1f}s")

            with col2:
                st.write("**Input:**")
                st.json(run['input_params'] or {})

            if run['output_summary']:
                st.write("**Output:**")
                st.json(run['output_summary'])

            if run['error_message']:
                st.error(f"**Error:** {run['error_message']}")


def show_deals():
    """Show funding deals."""
    st.header("💰 Funding Deals")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("Search by organization", placeholder="Enter organization name...")
    with col2:
        round_filter = st.selectbox("Round", ["All", "Seed", "Series A", "Series B", "Series C", "Series D+"])
    with col3:
        sort_by = st.selectbox("Sort by", ["Date (newest)", "Date (oldest)", "Amount (high to low)", "Amount (low to high)"])

    # Get deals
    with get_db() as db:
        query = db.query(Deal, Organization).join(
            Organization, Deal.org_id == Organization.id
        )

        if search:
            query = query.filter(Organization.name.ilike(f'%{search}%'))

        if round_filter != "All":
            if round_filter == "Series D+":
                query = query.filter(Deal.round.ilike('Series D%') | Deal.round.ilike('Series E%') | Deal.round.ilike('Series F%'))
            else:
                query = query.filter(Deal.round.ilike(f'%{round_filter}%'))

        if sort_by == "Date (newest)":
            query = query.order_by(desc(Deal.announced_on))
        elif sort_by == "Date (oldest)":
            query = query.order_by(Deal.announced_on)
        elif sort_by == "Amount (high to low)":
            query = query.order_by(desc(Deal.amount_usd))
        else:
            query = query.order_by(Deal.amount_usd)

        deals_data = query.limit(100).all()

        # Convert to dictionaries
        deals = []
        for deal, org in deals_data:
            deals.append({
                'id': str(deal.id),
                'org_name': org.name,
                'org_id': str(org.id),
                'round': deal.round,
                'amount_usd': float(deal.amount_usd) if deal.amount_usd else None,
                'amount_original': float(deal.amount_original) if deal.amount_original else None,
                'currency_original': deal.currency_original,
                'announced_on': deal.announced_on,
                'investors': deal.investors,
                'source': deal.source,
                'created_at': deal.created_at
            })

    if not deals:
        st.info("No deals found. Load some deals first: `make load-deals`")
        return

    # Display count
    st.caption(f"Showing {len(deals)} deals")

    # Display deals
    for deal in deals:
        # Format amount (values are in millions already)
        if deal['amount_usd']:
            amount_str = f"${deal['amount_usd']:,.1f}M"
        elif deal['amount_original'] and deal['currency_original']:
            amount_str = f"{deal['currency_original']} {deal['amount_original']:,.1f}M"
        else:
            amount_str = "Undisclosed"

        # Format date
        date_str = deal['announced_on'].strftime('%Y-%m-%d') if deal['announced_on'] else "Unknown date"

        with st.expander(f"{deal['org_name']} • {deal['round'] or 'Unknown round'} • {amount_str} • {date_str}"):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**Organization:** {deal['org_name']}")
                st.write(f"**Round:** {deal['round'] or 'Unknown'}")
                st.write(f"**Amount (USD):** {amount_str}")
                if deal['amount_original'] and deal['currency_original']:
                    st.write(f"**Original Amount:** {deal['currency_original']} {deal['amount_original']:,.1f}M")
                st.write(f"**Announced:** {date_str}")

                # Investors
                if deal['investors']:
                    st.write(f"**Investors ({len(deal['investors'])}):**")
                    for investor in deal['investors'][:10]:  # Show first 10
                        st.write(f"  • {investor}")
                    if len(deal['investors']) > 10:
                        st.write(f"  ... and {len(deal['investors']) - 10} more")

            with col2:
                st.write("**Source:**")
                source_name = deal['source'].get('name', 'Unknown')
                source_url = deal['source'].get('url', '')
                if source_url:
                    st.write(f"[{source_name}]({source_url})")
                else:
                    st.write(source_name)

                st.write(f"**Added:** {deal['created_at'].strftime('%Y-%m-%d')}")


# Agent execution functions
def run_website_finder(vc_name=None):
    """Run website finder agent."""
    agent_key = f"website_finder_{vc_name or 'all'}"

    if agent_key in st.session_state.running_agents:
        st.warning("Agent is already running!")
        return

    st.session_state.running_agents.add(agent_key)

    try:
        with st.spinner(f"Finding website for {vc_name or 'all VCs'}..."):
            from src.agents.vc_website_finder import VCWebsiteFinder
            finder = VCWebsiteFinder()

            if vc_name:
                # Process specific VC
                with get_db() as db:
                    from sqlalchemy import select
                    stmt = select(Organization).where(
                        Organization.kind == "vc",
                        Organization.name.ilike(f"%{vc_name}%")
                    )
                    vc = db.execute(stmt).scalar_one_or_none()

                    if not vc:
                        st.error(f"VC not found: {vc_name}")
                        return

                    stats = finder.find_and_update_website(vc, db, force=False)
                    st.success(f"✅ Website finder completed for {vc_name}!")
                    st.json(stats)
            else:
                # Process all VCs
                stats = finder.find_all_vc_websites(limit=None, force=False)
                st.success("✅ Website finder completed for all VCs!")
                st.json(stats)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        st.session_state.running_agents.discard(agent_key)


def run_vc_crawler(vc_name=None):
    """Run VC crawler agent."""
    agent_key = f"vc_crawler_{vc_name or 'all'}"

    if agent_key in st.session_state.running_agents:
        st.warning("Agent is already running!")
        return

    st.session_state.running_agents.add(agent_key)

    try:
        with st.spinner(f"Crawling {vc_name or 'all VCs'}..."):
            from src.agents.vc_crawler import VCCrawler
            crawler = VCCrawler()

            if vc_name:
                # Process specific VC
                with get_db() as db:
                    from sqlalchemy import select
                    stmt = select(Organization).where(
                        Organization.kind == "vc",
                        Organization.name.ilike(f"%{vc_name}%")
                    )
                    vc = db.execute(stmt).scalar_one_or_none()

                    if not vc:
                        st.error(f"VC not found: {vc_name}")
                        return

                    if not vc.website:
                        st.error(f"VC {vc_name} doesn't have a website yet. Run website finder first!")
                        return

                    stats = crawler.crawl_vc(vc)
                    st.success(f"✅ Crawler completed for {vc_name}!")
                    st.json(stats)
            else:
                # Process all VCs
                stats = crawler.crawl_all_vcs(limit=None)
                st.success("✅ Crawler completed for all VCs!")
                st.json(stats)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        st.session_state.running_agents.discard(agent_key)


def run_social_enricher(person_name=None):
    """Run social enricher agent."""
    agent_key = f"social_enricher_{person_name or 'all'}"

    if agent_key in st.session_state.running_agents:
        st.warning("Agent is already running!")
        return

    st.session_state.running_agents.add(agent_key)

    try:
        with st.spinner(f"Enriching {person_name or 'all people'}..."):
            from src.agents.social_enricher import SocialEnricher
            enricher = SocialEnricher()

            if person_name:
                # Process specific person
                with get_db() as db:
                    from sqlalchemy import select
                    stmt = select(Person, Organization).join(
                        RoleEmployment, Person.id == RoleEmployment.person_id
                    ).join(
                        Organization, RoleEmployment.org_id == Organization.id
                    ).where(
                        Person.full_name.ilike(f"%{person_name}%")
                    )
                    result = db.execute(stmt).first()

                    if not result:
                        st.error(f"Person {person_name} not found")
                        return

                    person, org = result
                    stats = enricher.enrich_person(person, org.name)
                    st.success(f"✅ Enrichment completed for {person_name}!")
                    st.json(stats)
            else:
                # Process all people
                stats = enricher.enrich_all_people(limit=None)
                st.success("✅ Enrichment completed for all people!")
                st.json(stats)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        st.session_state.running_agents.discard(agent_key)


def main():
    """Main application."""
    init_session_state()

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Organizations", "People", "Deals", "Agent Runs"],
        label_visibility="collapsed"
    )

    st.sidebar.divider()

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.session_state.last_refresh = datetime.now()
        st.rerun()

    st.sidebar.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

    # Show selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Organizations":
        show_orgs()
    elif page == "People":
        show_people()
    elif page == "Deals":
        show_deals()
    elif page == "Agent Runs":
        show_agent_runs()


if __name__ == "__main__":
    main()
