from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import Institution


User = get_user_model()


class SignupForm(UserCreationForm):
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(is_active=True).order_by("name"),
        empty_label="Select institution",
        required=True,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "institution")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "email" in self.fields:
            self.fields["email"].required = True
