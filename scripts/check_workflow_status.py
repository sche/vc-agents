#!/usr/bin/env python3
"""
Check workflow status for VCs.

Shows which VCs have been processed, which failed, and where they're stuck.
"""

from datetime import datetime

from loguru import logger
from sqlalchemy import desc, select
from tabulate import tabulate

from src.db.connection import get_db
from src.db.models import AgentRun, Organization


def check_workflow_status(agent_name: str | None = None, status: str | None = None):
    """
    Check workflow status for all VCs.

    Args:
        agent_name: Filter by agent name (e.g., 'vc_crawler', 'vc_website_finder')
        status: Filter by status (e.g., 'completed', 'failed', 'running')
    """
    with get_db() as db:
        # Get all VCs
        vc_stmt = select(Organization).where(Organization.kind == "vc")
        vcs = {str(vc.id): vc for vc in db.execute(vc_stmt).scalars().all()}

        # Get latest run for each VC/agent combination
        runs_stmt = select(AgentRun).order_by(desc(AgentRun.started_at))

        if agent_name:
            runs_stmt = runs_stmt.where(AgentRun.agent_name == agent_name)
        if status:
            runs_stmt = runs_stmt.where(AgentRun.status == status)

        runs = db.execute(runs_stmt).scalars().all()

        # Group runs by org_id and get the latest for each
        latest_runs = {}
        for run in runs:
            org_id = run.input_params.get("org_id") if run.input_params else None
            if org_id:
                key = f"{org_id}_{run.agent_name}"
                if key not in latest_runs or run.started_at > latest_runs[key].started_at:
                    latest_runs[key] = run

        # Prepare data for display
        table_data = []

        for vc_id, vc in vcs.items():
            # Find runs for this VC
            vc_runs = {
                agent: run
                for (org_agent, run) in latest_runs.items()
                if org_agent.startswith(vc_id)
                for agent in [org_agent.split('_', 1)[1]]
            }

            if not vc_runs:
                # No runs yet
                table_data.append([
                    vc.name[:30],
                    "❌ NOT STARTED",
                    "-",
                    "-",
                    "-",
                    "⚠️ No workflow runs"
                ])
            else:
                for agent, run in vc_runs.items():
                    status_icon = {
                        "completed": "✅",
                        "failed": "❌",
                        "running": "🔄",
                    }.get(run.status, "❓")

                    # Format duration
                    if run.completed_at:
                        duration = (run.completed_at - run.started_at).total_seconds()
                        duration_str = f"{duration:.1f}s"
                    else:
                        duration_str = "running..."

                    # Get key info from output or error
                    details = ""
                    if run.status == "failed" and run.error_message:
                        details = run.error_message[:40]
                    elif run.output_summary:
                        if agent == "vc_crawler":
                            people = run.output_summary.get("people_created", 0)
                            skipped = run.output_summary.get("people_skipped", 0)
                            details = f"{people} created, {skipped} skipped"
                        elif agent == "vc_website_finder":
                            website = run.output_summary.get("website")
                            details = website[:40] if website else "No website"

                    table_data.append([
                        vc.name[:30],
                        f"{status_icon} {run.status.upper()}",
                        agent,
                        run.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                        duration_str,
                        details
                    ])

        # Display results
        headers = ["VC Name", "Status", "Agent", "Started At", "Duration", "Details"]
        print("\n" + "="*120)
        print(f"📊 Workflow Status Report")
        if agent_name:
            print(f"   Agent: {agent_name}")
        if status:
            print(f"   Status: {status}")
        print("="*120 + "\n")

        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Summary
        print(f"\n📈 Summary:")
        print(f"   Total VCs: {len(vcs)}")
        print(f"   VCs with runs: {len([r for r in latest_runs.values()])}")
        print(f"   Completed: {len([r for r in latest_runs.values() if r.status == 'completed'])}")
        print(f"   Failed: {len([r for r in latest_runs.values() if r.status == 'failed'])}")
        print(f"   Running: {len([r for r in latest_runs.values() if r.status == 'running'])}")

        # Failed VCs that need attention
        failed_runs = [r for r in latest_runs.values() if r.status == "failed"]
        if failed_runs:
            print(f"\n⚠️  VCs Requiring Manual Intervention:")
            for run in failed_runs:
                org_id = run.input_params.get("org_id")
                vc_name = vcs.get(org_id).name if org_id in vcs else "Unknown"
                print(f"   • {vc_name}: {run.error_message}")


def show_vc_detail(vc_name: str):
    """Show detailed workflow history for a specific VC."""
    with get_db() as db:
        # Find VC
        stmt = select(Organization).where(
            Organization.kind == "vc",
            Organization.name.ilike(f"%{vc_name}%")
        )
        vc = db.execute(stmt).scalar_one_or_none()

        if not vc:
            print(f"❌ VC not found: {vc_name}")
            return

        # Get all runs for this VC
        runs_stmt = (
            select(AgentRun)
            .order_by(desc(AgentRun.started_at))
        )

        all_runs = []
        for run in db.execute(runs_stmt).scalars().all():
            if run.input_params and run.input_params.get("org_id") == str(vc.id):
                all_runs.append(run)

        print(f"\n{'='*100}")
        print(f"📋 Workflow History: {vc.name}")
        print(f"{'='*100}\n")

        if not all_runs:
            print("⚠️  No workflow runs found for this VC")
            return

        table_data = []
        for run in all_runs:
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "running": "🔄",
            }.get(run.status, "❓")

            duration = ""
            if run.completed_at:
                duration = f"{(run.completed_at - run.started_at).total_seconds():.1f}s"

            table_data.append([
                run.agent_name,
                f"{status_icon} {run.status}",
                run.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                duration,
                run.error_message or "-",
                str(run.output_summary) if run.output_summary else "-"
            ])

        headers = ["Agent", "Status", "Started At", "Duration", "Error", "Output"]
        print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[15, 15, 20, 10, 40, 40]))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check VC workflow status")
    parser.add_argument("--agent", help="Filter by agent name")
    parser.add_argument("--status", choices=["completed", "failed", "running"], help="Filter by status")
    parser.add_argument("--vc", help="Show detailed history for a specific VC")

    args = parser.parse_args()

    if args.vc:
        show_vc_detail(args.vc)
    else:
        check_workflow_status(args.agent, args.status)
