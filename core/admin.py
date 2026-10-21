from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
admin.site.register(User, UserAdmin)
for m in (SeniorProfile, VolunteerProfile, VerificationRecord, Category, HelpRequest, Assignment, Complaint):
    admin.site.register(m)
admin.site.register(ActivityLog)
