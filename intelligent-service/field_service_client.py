import httpx

class FieldServiceClient:
    """
    Client per interagire con il servizio field-service.
    Attributes:
        client (httpx.AsyncClient): Istanza di httpx.AsyncClient per effettuare le richieste al servizio field-service
    """
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
    
    async def get_latest_readings(self, field: str, sensor_types: list[str], window_size: int, token: str) -> list[dict]:
        """
        Permette di ottenere le ultime letture dei sensori del tipo indicato, fino al numero massimo specificato, per il campo indicato.
        Args:
            field (str): Nome del campo da cui recuperare le letture
            sensor_types (list[str]): Lista dei tipi di sensori di cui recuperare le letture
            window_size (int): Numero massimo di letture da recuperare per ogni tipo di sensore
            token (str): Token di autorizzazione jwt Bearer
        Returns:
            Lista di dizionari contenenti le letture dei sensori
        """
        url = f"/fields/{field}/specific-types-readings"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "sensor_types": sensor_types,
            "limit": window_size
        }
        
        
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()