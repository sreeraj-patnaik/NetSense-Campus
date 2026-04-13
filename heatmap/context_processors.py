from .models import InstitutionMembership


def institution_access(request):
    user = getattr(request, "user", None)
    is_institution_admin = False
    if user and user.is_authenticated:
        if user.is_staff or user.is_superuser:
            is_institution_admin = True
        else:
            is_institution_admin = InstitutionMembership.objects.filter(
                user=user,
                status=InstitutionMembership.APPROVED,
                role=InstitutionMembership.ADMIN,
            ).exists()
    return {"is_institution_admin": is_institution_admin}
