from sqlalchemy import select
from models import Rule
import json

CACHE_TTL_RULES_LIST = 30 * 60

async def get_rules_for_field(field: str, db, redis=None):
    
    cache_key = f"rules_list:{field}"

    if redis:
        try:
            cached_rules = await redis.get(cache_key)
            if cached_rules:
                return json.loads(cached_rules) 
        except Exception:
            print("Errore nel recupero delle regole dalla cache.")

    result = await db.execute(select(Rule).where(Rule.field == field))
    rules = result.scalars().all()

    if redis:
        try:
            rules_dict_list = [
                {
                    "rule_name": rule.rule_name,
                    "sensor_type": rule.sensor_type,
                    "condition": rule.condition,
                    "threshold": rule.threshold,
                    "message": rule.message,
                    "field": rule.field,
                    "owner_id": rule.owner_id
                }
                for rule in rules
            ]
            await redis.set(cache_key, json.dumps(rules_dict_list), ex=CACHE_TTL_RULES_LIST)
        except Exception:
            print("Errore nel salvataggio delle regole nella cache.")
    
    return rules_dict_list

def violated_rule(condition: str, sensor_value: float, threshold: float) -> bool:
    if condition == ">":
        return sensor_value > threshold
    elif condition == "<":
        return sensor_value < threshold
    elif condition == "==":
        return sensor_value == threshold
    else:
        raise ValueError(f"Condizione non valida: {condition}")