from fastapi import APIRouter


router = APIRouter(tags=["Saúde"])


@router.get("/health")
def verificar_saude() -> dict[str, str]:
    """Usado pelo Render e por monitoramento para saber se a API está no ar."""
    return {"service": "auth-service", "status": "healthy"}
