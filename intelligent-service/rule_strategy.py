from rules_service import get_rules_for_field, violated_rule
from base import AnalysisStrategy
from contexts import RuleAnalysisContext

class RuleBasedStrategy(AnalysisStrategy[RuleAnalysisContext]):

    async def analyze(self, context: RuleAnalysisContext):

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