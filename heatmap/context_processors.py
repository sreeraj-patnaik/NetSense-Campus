from .models import InstitutionMembership


def _current_membership(user):
    if not user or not user.is_authenticated:
        return None
    return (
        InstitutionMembership.objects.select_related("institution")
        .filter(user=user, status=InstitutionMembership.APPROVED)
        .order_by("institution__name")
        .first()
    )


def institution_access(request):
    user = getattr(request, "user", None)
    is_institution_admin = False
    current_institution = None
    can_scan = False
    if user and user.is_authenticated:
        if user.is_staff or user.is_superuser:
            is_institution_admin = True
        else:
            is_institution_admin = InstitutionMembership.objects.filter(
                user=user,
                status=InstitutionMembership.APPROVED,
                role=InstitutionMembership.ADMIN,
            ).exists()
        membership = _current_membership(user)
        if membership:
            current_institution = membership.institution
            can_scan = membership.can_scan or membership.role == InstitutionMembership.ADMIN
    display_name = ""
    email = ""
    if user and getattr(user, "is_authenticated", False):
        full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
        display_name = full_name or getattr(user, "username", "")
        email = getattr(user, "email", "")

    return {
        "is_institution_admin": is_institution_admin,
        "current_institution_name": current_institution.name if current_institution else "",
        "current_institution_code": current_institution.code if current_institution else "",
        "current_user_display": display_name,
        "current_user_email": email,
        "current_user_can_scan": can_scan,
    }
