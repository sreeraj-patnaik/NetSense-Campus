import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from .aggregation import refresh_cell_aggregates
from .chatbot import route_chatbot_request
from . import context_processors, views
from .models import Block, FloorPlan, Institution, InstitutionMembership, Scan, UserDashboardPreference


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
            role=InstitutionMembership.ADMIN,
        )
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.zeta,
            status=InstitutionMembership.PENDING,
            role=InstitutionMembership.MEMBER,
        )

        request = self.factory.get("/")
        request.user = self.user

        context = context_processors.institution_access(request)

        self.assertEqual(context["current_institution_name"], "Alpha Institute")
        self.assertEqual(context["current_institution_code"], "ALPHA")

    def test_viewer_context_defaults_to_admin_institution_block(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.ADMIN,
        )
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.zeta,
            status=InstitutionMembership.PENDING,
            role=InstitutionMembership.MEMBER,
        )

        context = views._viewer_context(self.user)

        self.assertEqual(context["initial_block"], "A")
        self.assertEqual(context["initial_floor"], 1)
        self.assertEqual(context["blocks"][0], "A")

    def test_dashboard_preferences_view_persists_selection(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
        )

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

    def _add_session(self, request):
        middleware = SessionMiddleware(lambda _request: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_config_api_filters_blocks_to_current_institution(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.ADMIN,
        )
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.zeta,
            status=InstitutionMembership.PENDING,
            role=InstitutionMembership.MEMBER,
        )

        request = self.factory.get("/api/config/")
        request.user = self.user

        response = views.config_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["blocks"], ["A"])
        self.assertEqual(payload["block_floors"]["A"], [1])

    def test_heatmap_api_blocks_other_institution_floor(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
        )

        request = self.factory.get("/api/heatmap/?block=Z&floor=1&mode=wifi")
        request.user = self.user

        response = views.heatmap_api(request)

        self.assertEqual(response.status_code, 403)

    def test_chatbot_asks_for_missing_analytics_context(self):
        InstitutionMembership.objects.create(
            user=self.user,
            institution=self.alpha,
            status=InstitutionMembership.APPROVED,
            role=InstitutionMembership.MEMBER,
        )
        request = self._add_session(self.factory.post("/api/chatbot/"))
        request.user = self.user

        result = route_chatbot_request(
            request,
            "Which provider gives best signal?",
            [],
            {},
        )

        self.assertEqual(result["mode"], "analytics")
        self.assertIn("Which block, floor, and provider type", result["answer"])
        self.assertTrue(result["choices"])
        self.assertTrue(any(choice["label"].startswith("Block") for choice in result["choices"]))

    def test_chatbot_general_mode_skips_analytics(self):
        request = self._add_session(self.factory.post("/api/chatbot/"))
        request.user = self.user

        result = route_chatbot_request(request, "Hello there", [], {})

        self.assertEqual(result["mode"], "general")

    def test_chatbot_requires_sign_in_for_institution_question(self):
        request = self._add_session(self.factory.post("/api/chatbot/"))
        request.user = self.user

        result = route_chatbot_request(request, "whats my instt name", [], {})

        self.assertEqual(result["mode"], "auth")
        self.assertIn("sign in", result["answer"].lower())
        self.assertTrue(any(choice.get("href") for choice in result["choices"]))

    def test_chatbot_explains_app_purpose_without_hallucination(self):
        request = self._add_session(self.factory.post("/api/chatbot/"))
        request.user = self.user

        result = route_chatbot_request(request, "what's this app for", [], {})

        self.assertEqual(result["mode"], "general")
        self.assertIn("network coverage", result["answer"].lower())
        self.assertTrue(any(choice["label"] == "Live coverage" for choice in result["choices"]))
        self.assertTrue(
            any(choice["label"] in {"Sign in", "My institution"} for choice in result["choices"])
        )

    def test_greeting_clears_pending_analytics_state(self):
        request = self._add_session(self.factory.post("/api/chatbot/"))
        request.user = self.user
        request.session["netsense_chatbot_pending"] = {
            "intent": "comparison",
            "scope": {"block": "A"},
        }
        request.session.save()

        result = route_chatbot_request(request, "hello dear", [], {})

        self.assertEqual(result["mode"], "general")
        self.assertNotIn("netsense_chatbot_pending", request.session)

    def test_chatbot_api_greeting_uses_canned_response(self):
        request = self._add_session(
            self.factory.post(
                "/api/chatbot/",
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )
        )
        request.user = self.user

        response = views.chatbot_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("Spen Sense", payload["answer"])
        self.assertNotIn("project assistant", payload["answer"].lower())

    def test_general_answer_sanitizer_blocks_project_hallucination(self):
        answer = views._sanitize_general_assistant_answer(
            "Hi, I'm Spen Sense. I'm the NetSense Campus project assistant that helps students manage their time.",
            "hello",
        )

        self.assertIn("spen sense", answer.lower())
        self.assertNotIn("project assistant", answer.lower())

    def test_general_chat_messages_use_strict_system_prompt(self):
        messages = views._build_general_chat_messages(
            "Explain Python",
            [{"role": "assistant", "text": "Sure"}],
        )

        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Never invent", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Explain Python")

    @patch("heatmap.views._call_groq", return_value=(None, "down"))
    @patch("heatmap.views._call_ollama", return_value=(None, "down"))
    def test_chatbot_api_uses_safe_fallback_when_models_fail(self, _ollama, _groq):
        request = self._add_session(
            self.factory.post(
                "/api/chatbot/",
                data=json.dumps({"message": "Hello"}),
                content_type="application/json",
            )
        )
        request.user = self.user

        response = views.chatbot_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("spen sense", payload["answer"].lower())
