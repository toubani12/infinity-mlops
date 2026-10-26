from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.schemas import Health, ModelInfo, PredictRequest, PredictResponse
from app.inference.service import InferenceService, ModelUnavailableError, Transaction

router = APIRouter()


def service_of(request: Request) -> InferenceService:
    return request.app.state.service


def model_info(service: InferenceService) -> ModelInfo:
    model = service.model
    if model is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "no champion model loaded")
    return ModelInfo(
        model_name=model.name,
        version=model.version,
        alias=model.alias,
        loaded_at=model.loaded_at,
        threshold=service.threshold,
        last_reload_error=service.last_reload_error,
    )


@router.post("/predict", response_model=PredictResponse, operation_id="predict")
def predict(body: PredictRequest, request: Request) -> PredictResponse:
    transaction = Transaction(
        transaction_id=str(body.transaction_id),
        timestamp=body.timestamp or datetime.now(UTC),
        features=body.features | {"amount": body.amount},
    )
    try:
        (score,) = service_of(request).score([transaction], source="api")
    except ModelUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return PredictResponse(
        transaction_id=body.transaction_id,
        fraud_score=score.fraud_score,
        is_fraud=score.is_fraud,
        threshold=score.threshold,
        model_name=score.model_name,
        model_version=score.model_version,
        latency_ms=score.latency_ms,
    )


@router.get("/model", response_model=ModelInfo, operation_id="currentModel")
def current_model(request: Request) -> ModelInfo:
    return model_info(service_of(request))


@router.post("/model/reload", response_model=ModelInfo, operation_id="reloadModel")
async def reload_model(request: Request) -> ModelInfo:
    service = service_of(request)
    try:
        await service.reload()
    except ModelUnavailableError as error:
        detail = f"registry unreachable, previous model kept ({service.describe()}): {error}"
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail) from error
    return model_info(service)


@router.get("/health", response_model=Health, operation_id="health")
def health(request: Request) -> Health:
    loaded = service_of(request).model is not None
    return Health(status="ok" if loaded else "degraded", model_loaded=loaded)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
