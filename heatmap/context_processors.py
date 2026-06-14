from .services import current_institution, is_institution_admin, user_can_scan


def institution_access(request):
    user = getattr(request, "user", None)
    institution = None
    can_scan = False
    if user and user.is_authenticated:
        institution = current_institution(user)
        can_scan = user_can_scan(user)
    display_name = ""
    email = ""
    if user and getattr(user, "is_authenticated", False):
        full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
        display_name = full_name or getattr(user, "username", "")
        email = getattr(user, "email", "")

    return {
        "is_institution_admin": is_institution_admin(user),
        "current_institution_name": institution.name if institution else "",
        "current_institution_code": institution.code if institution else "",
        "current_user_display": display_name,
        "current_user_email": email,
        "current_user_can_scan": can_scan,
    }
