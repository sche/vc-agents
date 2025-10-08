#!/usr/bin/env python3
"""
FastAPI server for triggering agents from Retool.
"""

from fastapi import BackgroundTasks, FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.agents.social_enricher import SocialEnricher
from src.agents.vc_crawler import VCCrawler
from src.agents.vc_website_finder import VCWebsiteFinder
from src.db.connection import get_db
from src.db.models import Organization

app = FastAPI(title="VC Agents API")


class WebsiteFinderRequest(BaseModel):
    vc_name: str | None = None
    limit: int | None = None


class CrawlerRequest(BaseModel):
    vc_name: str | None = None
    use_fallback: bool = True


class EnricherRequest(BaseModel):
    limit: int | None = None


@app.get("/")
def root():
    return {"status": "ok", "service": "vc-agents-api"}


@app.post("/agents/find-websites")
async def run_website_finder(request: WebsiteFinderRequest, background_tasks: BackgroundTasks):
    """Find VC websites."""
    logger.info(f"Starting website finder: {request}")

    finder = VCWebsiteFinder()

    if request.vc_name:
        # Find specific VC
        with get_db() as db:
            org = db.query(Organization).filter(
                Organization.name.ilike(f"%{request.vc_name}%")
            ).first()

            if not org:
                raise HTTPException(status_code=404, detail=f"VC not found: {request.vc_name}")

            result = finder.find_website(org)
            return {"status": "completed", "result": result}
    else:
        # Find all
        stats = finder.find_all_websites(limit=request.limit)
        return {"status": "completed", "stats": stats}


@app.post("/agents/crawl")
async def run_crawler(request: CrawlerRequest, background_tasks: BackgroundTasks):
    """Crawl VC team pages."""
    logger.info(f"Starting crawler: {request}")

    crawler = VCCrawler(use_fallback=request.use_fallback)

    if request.vc_name:
        # Crawl specific VC
        with get_db() as db:
            org = db.query(Organization).filter(
                Organization.name.ilike(f"%{request.vc_name}%")
            ).first()

            if not org:
                raise HTTPException(status_code=404, detail=f"VC not found: {request.vc_name}")

            result = crawler.crawl_vc(org)
            return {"status": "completed", "result": result}
    else:
        # Crawl all
        stats = crawler.crawl_all_vcs()
        return {"status": "completed", "stats": stats}


@app.post("/agents/enrich")
async def run_enricher(request: EnricherRequest, background_tasks: BackgroundTasks):
    """Enrich people with social handles."""
    logger.info(f"Starting enricher: {request}")

    enricher = SocialEnricher()
    stats = enricher.enrich_all_people(limit=request.limit)

    return {"status": "completed", "stats": stats}


@app.get("/vcs")
def list_vcs(limit: int = 100):
    """List VCs in database."""
    with get_db() as db:
        orgs = db.query(Organization).filter(
            Organization.kind == "vc"
        ).limit(limit).all()

        return {
            "total": len(orgs),
            "vcs": [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "website": org.website,
                }
                for org in orgs
            ]
        }


@app.get("/agent-runs")
def list_agent_runs(limit: int = 50):
    """List recent agent runs."""
    from src.db.models import AgentRun

    with get_db() as db:
        runs = db.query(AgentRun).order_by(
            AgentRun.started_at.desc()
        ).limit(limit).all()

        return {
            "total": len(runs),
            "runs": [
                {
                    "id": str(run.id),
                    "agent_name": run.agent_name,
                    "status": run.status,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "output_summary": run.output_summary,
                }
                for run in runs
            ]
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
