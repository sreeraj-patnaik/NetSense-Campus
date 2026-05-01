from .models import InstitutionMembership, UserDashboardPreference


def _current_membership(user):
    if not user or not user.is_authenticated:
        return None
    memberships = InstitutionMembership.objects.select_related("institution").filter(
        user=user,
        status=InstitutionMembership.APPROVED,
    )
    admin_membership = memberships.filter(role=InstitutionMembership.ADMIN).order_by(
        "-approved_at",
        "-created_at",
    ).first()
    if admin_membership:
        return admin_membership
    return memberships.order_by("-approved_at", "-created_at").first()


def _selected_institution(user):
    if not user or not user.is_authenticated:
        return None
    preference = UserDashboardPreference.objects.select_related("selected_institution").filter(user=user).first()
    if preference and preference.selected_institution:
        return preference.selected_institution
    membership = _current_membership(user)
    return membership.institution if membership else None


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
        current_institution = _selected_institution(user)
        if membership:
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
