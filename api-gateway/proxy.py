import httpx
from fastapi import Response

async def proxy_request(request, target_base_url, forward_path):
    """
    Proxy per inoltrare le richieste HTTP ai servizi di backend.
    Esclude alcune intestazioni non necessarie.
    Args:
        request: Oggetto della richiesta FastAPI.
        target_base_url: URL base del servizio di destinazione.
        forward_path: Path da inoltrare al servizio di destinazione.
    Returns:
        Risposta dal servizio di destinazione. Esclude alcune intestazioni non necessarie.
    """

    headers = dict(request.headers)
    headers.pop("host", None) 
    headers.pop("content-length", None)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(
            method=request.method,
            url=f"{target_base_url}/{forward_path}",
            headers=dict(request.headers),
            params=request.query_params,
            content=await request.body()
        )

    excluded_headers = {"content-encoding", "transfer-encoding", "connection"}
    headers = {key: value for key, value in resp.headers.items() if key.lower() not in excluded_headers}

    return Response(content=resp.content, status_code=resp.status_code, headers=headers)