from sqlalchemy import Column, Integer, String, Double, Computed, UniqueConstraint, DateTime, Boolean, Index, text
from database import Base

class Rule(Base):
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String, Computed("('rule' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    sensor_type = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    threshold = Column(Double, nullable=False)
    message = Column(String, nullable=False)
    field = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('sensor_type', 'condition', 'threshold', 'message', 'field', 'owner_id', name='uix_rule_unique_per_user'),
    )

class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, index=True)
    alert_name = Column(String, Computed("('alert' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    sensor_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    field = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

    __table_args__ = (
        Index("id_alerts_active_owner", "owner_id", "timestamp", postgresql_where=text("active = true"),),
        Index("idx_alerts_active_owner_field_ts", "owner_id", "field", "timestamp", postgresql_where=text("active = true"),),
    )