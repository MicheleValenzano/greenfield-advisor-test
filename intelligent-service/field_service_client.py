import httpx

"""
Client per interagire con il servizio field-service.
:param client: Istanza di httpx.AsyncClient per effettuare le richieste al servizio field-service
"""
class FieldServiceClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
    
    """
    Permette di ottenere le ultime letture dei sensori del tipo indicato, fino al numero massimo specificato, per il campo indicato.
    :param field: Nome del campo
    :param sensor_types: Lista dei tipi di sensori da recuperare
    :param window_size: Numero massimo di letture da recuperare per ogni tipo di sensore
    :param token: Token di autorizzazione jwt Bearer
    :return: Lista di dizionari contenenti le letture dei sensori
    """
    async def get_latest_readings(self, field: str, sensor_types: list[str], window_size: int, token: str) -> list[dict]:
        url = f"/fields/{field}/specific-types-readings"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "sensor_types": sensor_types,
            "limit": window_size
        }
        
        
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()