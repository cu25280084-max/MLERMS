from models.audit_model import create_audit_log


create_audit_log(
    user_id=1,
    action="TEST",
    module="SYSTEM",
    record_id="TEST-001",
    description="Audit logging test record"
)

print("Audit log created successfully.")