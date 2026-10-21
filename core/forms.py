from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *

def _check_doc(d):
    if d.size > 5 * 1024 * 1024: raise forms.ValidationError("File too large (max 5 MB).")
    if not d.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
        raise forms.ValidationError("Only PDF, JPG or PNG allowed.")
    return d

class RegisterForm(UserCreationForm):
    phone = forms.RegexField(r"^\+?\d{10,13}$", error_messages={"invalid": "Enter a valid phone number (10-13 digits)."})
    age = forms.IntegerField(required=False, min_value=1, max_value=120)
    occupation = forms.CharField(required=False, max_length=100)
    document = forms.FileField()
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "address"]
    def __init__(self, *a, role="senior", **k):
        super().__init__(*a, **k); self.role = role
        if role == "senior": del self.fields["occupation"]
        else: del self.fields["age"]
        for n in ("first_name", "last_name", "address"): self.fields[n].required = True
    def clean_document(self): return _check_doc(self.cleaned_data["document"])

class RequestForm(forms.ModelForm):
    class Meta:
        model = HelpRequest
        fields = ["category", "description", "required_date", "preferred_time", "location", "instructions"]
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["category"].queryset = Category.objects.filter(active=True)
    def clean_required_date(self):
        from datetime import date
        d = self.cleaned_data["required_date"]
        if d < date.today(): raise forms.ValidationError("Date cannot be in the past.")
        return d

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category; fields = ["name", "name_hi", "name_mr", "description", "active"]

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint; fields = ["request", "description"]
    def __init__(self, *a, user=None, **k):
        super().__init__(*a, **k)
        from django.db.models import Q
        self.fields["request"].required = False
        self.fields["request"].queryset = (HelpRequest.objects.filter(Q(senior=user) | Q(assignments__volunteer=user)).distinct()
                                           if user else HelpRequest.objects.none())

class ResubmitForm(forms.Form):
    document = forms.FileField()
    def clean_document(self): return _check_doc(self.cleaned_data["document"])

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User; fields = ["first_name", "last_name", "email", "phone", "address"]
