from rules_service import get_rules_for_field, violated_rule
from base import AnalysisStrategy
from contexts import RuleAnalysisContext

class RuleBasedStrategy(AnalysisStrategy[RuleAnalysisContext]):
    """
    Strategy per l'analisi basata su regole.
    Implementa il metodo di analisi che valuta i dati in ingresso
    rispetto a un insieme di regole definite dall'utente.
    Utilizza funzioni esterne per recuperare le regole e verificare
    se i dati violano tali regole.
    """

    async def analyze(self, context: RuleAnalysisContext):
        """
        Analizza i dati in ingresso confrontandoli con le regole definite.
        Restituisce un elenco di regole che sono state violate dai dati.
        Args:
            context (RuleAnalysisContext): Contesto contenente i dati da analizzare e le risorse necessarie.
        Returns:
            List[Dict]: Elenco delle regole violate.
        """
        payload = context.payload
        db = context.db
        redis = context.redis

        rules = await get_rules_for_field(field=payload["field_id"], db=db, redis=redis)

        alerts = []

        for rule in rules:
            if rule["sensor_type"] == payload["sensor_type"]:

                print("Evaluating rule:", rule, "with payload type:", payload["sensor_type"])

                if violated_rule(rule["condition"], payload["value"], rule["threshold"]):
                    print(f"Alert! Rule {rule} not satisfied for payload {payload}") 
                    alerts.append(rule)

        return alerts