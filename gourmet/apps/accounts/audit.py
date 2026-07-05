from .models import AuditLog


def log_audit(request, action, target="", detail=""):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        target=target,
        detail=detail,
        ip=request.META.get("REMOTE_ADDR"),
    )
