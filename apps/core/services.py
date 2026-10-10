from .models import AuditEvent

def audit(actor, action, obj=None, details=None):
    return AuditEvent.objects.create(actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action, object_type=obj._meta.label if obj is not None else '',
        object_id=str(obj.pk) if obj is not None else '', details=details or {})
