from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from . import context_processors, views
from .models import Block, FloorPlan, Institution, InstitutionMembership, UserDashboardPreference


User = get_user_model()


class InstitutionSelectionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="alex", password="pass12345")

        self.alpha = Institution.objects.create(name="Alpha Institute", code="ALPHA")
        self.zeta = Institution.objects.create(name="Zeta Institute", code="ZETA")

        self.alpha_block = Block.objects.create(institution=self.alpha, code="A", name="Alpha Block")
        self.zeta_block = Block.objects.create(institution=self.zeta, code="Z", name="Zeta Block")

        FloorPlan.objects.create(block=self.alpha_block, number=1, grid_rows=12, grid_cols=8)
        FloorPlan.objects.create(block=self.zeta_block, number=1, grid_rows=12, grid_cols=8)

    def test_current_membership_prefers_admin_institution(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
        )
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.zeta,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.ADMIN,
        )

        request = self.factory.get("/")
        request.user = self.user

        context = context_processors.institution_access(request)

        self.assertEqual(context["current_institution_name"], "Zeta Institute")
        self.assertEqual(context["current_institution_code"], "ZETA")

    def test_viewer_context_defaults_to_admin_institution_block(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
        )
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.zeta,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.ADMIN,
        )

        context = views._viewer_context(self.user)

        self.assertEqual(context["initial_block"], "Z")
        self.assertEqual(context["initial_floor"], 1)
        self.assertEqual(context["blocks"][0], "Z")

    def test_dashboard_preferences_view_persists_selection(self):
        request = self.factory.post(
            "/dashboard-preferences/",
            {
                "selected_institution": str(self.alpha.id),
                "dashboard_preset": UserDashboardPreference.PRESET_CUSTOM,
                "compare_block": "A",
                "compare_floor": "1",
                "weak_threshold": "-78",
            },
        )
        request.user = self.user

        response = views.dashboard_preferences_view(request)

        self.assertEqual(response.status_code, 302)
        preference = UserDashboardPreference.objects.get(user=self.user)
        self.assertEqual(preference.selected_institution_id, self.alpha.id)
        self.assertEqual(preference.dashboard_preset, UserDashboardPreference.PRESET_CUSTOM)
        self.assertEqual(preference.compare_block, "A")
        self.assertEqual(preference.compare_floor, 1)
        self.assertEqual(preference.weak_threshold, -78)

    def test_dashboard_insights_api_blocks_unauthorized_floor_access(self):
        request = self.factory.get(
            "/api/dashboard-insights/?block=A&floor=1&mode=wifi",
        )
        request.user = self.user

        response = views.dashboard_insights_api(request)

        self.assertEqual(response.status_code, 403)

    def test_heatmap_access_allowed_without_scan_permission(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
            can_scan=False,
        )

        self.assertTrue(views._user_can_view_heatmap(self.user))
        self.assertFalse(views._user_can_scan(self.user))
