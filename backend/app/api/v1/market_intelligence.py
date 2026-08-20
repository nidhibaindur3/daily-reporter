from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_market_intelligence_service
from app.schemas.market_intelligence import (
    DiscoveryRunResponse,
    OpportunityProvenanceResponse,
    ResearchOpportunityListResponse,
    ResearchOpportunityResponse,
    StartDiscoveryRunRequest,
)
from app.services.market_intelligence import (
    MarketIntelligenceNotConfiguredError,
    MarketIntelligenceService,
)

router = APIRouter(prefix="/market-intelligence", tags=["market intelligence"])


@router.post(
    "/runs",
    response_model=DiscoveryRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_discovery_run(
    request: StartDiscoveryRunRequest,
    service: Annotated[
        MarketIntelligenceService, Depends(get_market_intelligence_service)
    ],
) -> DiscoveryRunResponse:
    try:
        run = service.start_run(
            window_hours=request.window_hours,
            maximum_themes=request.maximum_themes,
            focus_topics=tuple(request.focus_topics),
        )
    except MarketIntelligenceNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="market intelligence is not configured",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="market intelligence persistence unavailable",
        ) from exc
    return DiscoveryRunResponse.from_run(run)


@router.get("/runs/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery_run(
    run_id: str,
    service: Annotated[
        MarketIntelligenceService, Depends(get_market_intelligence_service)
    ],
) -> DiscoveryRunResponse:
    try:
        return DiscoveryRunResponse.from_run(service.get_run(run_id))
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="market intelligence run not found",
        ) from exc


@router.get("/opportunities", response_model=ResearchOpportunityListResponse)
def list_research_opportunities(
    service: Annotated[
        MarketIntelligenceService, Depends(get_market_intelligence_service)
    ],
    run_id: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ResearchOpportunityListResponse:
    records = service.list_opportunities(run_id, limit)
    return ResearchOpportunityListResponse(
        opportunities=[
            ResearchOpportunityResponse.from_record(
                record,
                service.sources_for_opportunity(record),
            )
            for record in records
        ]
    )


@router.get(
    "/opportunities/{opportunity_id}",
    response_model=ResearchOpportunityResponse,
)
def get_research_opportunity(
    opportunity_id: str,
    service: Annotated[
        MarketIntelligenceService, Depends(get_market_intelligence_service)
    ],
) -> ResearchOpportunityResponse:
    try:
        record = service.get_opportunity(opportunity_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="research opportunity not found",
        ) from exc
    return ResearchOpportunityResponse.from_record(
        record,
        service.sources_for_opportunity(record),
    )


@router.get(
    "/opportunities/{opportunity_id}/provenance",
    response_model=OpportunityProvenanceResponse,
)
def get_opportunity_provenance(
    opportunity_id: str,
    service: Annotated[
        MarketIntelligenceService, Depends(get_market_intelligence_service)
    ],
) -> OpportunityProvenanceResponse:
    try:
        return OpportunityProvenanceResponse.from_bundle(
            service.get_provenance(opportunity_id)
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="research opportunity not found",
        ) from exc
