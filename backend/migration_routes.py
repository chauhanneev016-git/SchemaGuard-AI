
"""FastAPI routes for migration impact analysis."""

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from backend.analyzers.migration_impact import analyze_migration


def create_migration_router(db):
    router = APIRouter(prefix="/api/migration", tags=["Migration"])

    @router.get("/impact")
    def migration_impact(
        target: str = Query(default="students_v3")
    ):
        try:
            return analyze_migration(db, target)

        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )

        except PyMongoError:
            raise HTTPException(
                status_code=503,
                detail="MongoDB migration analysis failed.",
            )

    return router
