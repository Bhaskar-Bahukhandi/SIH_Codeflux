from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InspectionFinalizationRead(BaseModel):
    id: str
    inspection_id: str
    finalized_by_user_id: str
    rule_evaluation_run_id: str
    rule_pack_id: str
    rule_pack_version: str
    rule_pack_sha256: str
    snapshot: dict
    snapshot_sha256: str
    report_id: str
    report_version: str
    report_sha256: str
    report_size_bytes: int
    finalized_at: datetime

    model_config = ConfigDict(from_attributes=True)
