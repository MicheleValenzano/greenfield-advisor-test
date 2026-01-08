from pydantic import BaseModel, Field, field_validator

admitted_conditions = {">", "<", "=="} # Condizioni ammesse per le regole

class RuleCreation(BaseModel):
    """
    Modello per la creazione di una regola intelligente.
    """
    sensor_type: str = Field(..., example="temperatura", description="Tipo di sensore a cui si applica la regola.")
    condition: str = Field(..., example=">", description="Condizione della regola, ad esempio '>', '<', '==', ecc...")
    threshold: float = Field(..., example=30.0, description="Valore soglia per attivare la regola.")
    message: str = Field(..., example="Regolare temperatura", description="Azione da eseguire quando la regola è soddisfatta.")
    field: str = Field(..., example="field1234", description="Campo a cui si applica la regola.")
    
    @field_validator("condition")
    def validate_condition(cls, value):
        if value not in admitted_conditions:
            raise ValueError(f"La condizione deve essere una delle seguenti: {', '.join(admitted_conditions)}")
        return value
    
    @field_validator("sensor_type")
    def validate_sensor_type(cls, value):
        if not value.strip():
            raise ValueError("Il tipo di sensore non può essere vuoto.")
        return value
    
    @field_validator("message")
    def validate_message(cls, value):
        if not value.strip():
            raise ValueError("Il messaggio non può essere vuoto.")
        return value
    
    @field_validator("field")
    def validate_field(cls, value):
        if not value.strip():
            raise ValueError("Il campo non può essere vuoto.")
        return value

class RuleOutput(BaseModel):
    """
    Modello per l'output di una regola intelligente.
    """
    rule_name: str
    sensor_type: str
    condition: str
    threshold: float
    field: str

    class Config:
        orm_mode = True