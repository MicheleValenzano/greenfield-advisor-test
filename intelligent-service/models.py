from sqlalchemy import Column, Integer, String, Double, Computed, UniqueConstraint, DateTime, Boolean, Index, text
from database import Base

class Rule(Base):
    """
    Schema del database di una regola per il monitoraggio dei sensori.
    Una regola definisce una condizione specifica che, se soddisfatta dai dati del sensore,
    genera un avviso (alert).

    Attributes:
        id (int): Identificatore univoco della regola.
        rule_name (str): Nome univoco della regola, generato automaticamente.
        sensor_type (str): Tipo di sensore a cui si applica la regola (es. temperatura, umidità).
        condition (str): Condizione da verificare (es. '>', '<', '==').
        threshold (float): Valore soglia per la condizione.
        message (str): Messaggio da inviare quando la regola viene attivata.
        field (str): Campo specifico del sensore a cui si applica la regola.
        owner_id (int): Identificatore dell'utente proprietario della regola.
    """
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String, Computed("('rule' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    sensor_type = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    threshold = Column(Double, nullable=False)
    message = Column(String, nullable=False)
    field = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Assicura che non esistano regole duplicate per lo stesso utente
    __table_args__ = (
        UniqueConstraint('sensor_type', 'condition', 'threshold', 'message', 'field', 'owner_id', name='uix_rule_unique_per_user'),
    )

class Alert(Base):
    """
    Schema del database di un avviso generato da una regola.
    Un avviso viene creato quando i dati del sensore soddisfano la condizione definita in una regola.
    Attributes:
        id (int): Identificatore univoco dell'avviso.
        alert_name (str): Nome univoco dell'avviso, generato automaticamente.
        sensor_type (str): Tipo di sensore che ha generato l'avviso.
        message (str): Messaggio associato all'avviso.
        timestamp (datetime): Data e ora in cui l'avviso è stato generato.
        active (bool): Stato dell'avviso (attivo o risolto).
        field (str): Campo specifico del sensore associato all'avviso.
        owner_id (int): Identificatore dell'utente proprietario dell'avviso.
    """
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, index=True)
    alert_name = Column(String, Computed("('alert' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    sensor_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    field = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Indici per ottimizzare le query sugli avvisi attivi per utente e campo
    __table_args__ = (
        Index("id_alerts_active_owner", "owner_id", "timestamp", postgresql_where=text("active = true"),),
        Index("idx_alerts_active_owner_field_ts", "owner_id", "field", "timestamp", postgresql_where=text("active = true"),),
    )