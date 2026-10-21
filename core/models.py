from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

class User(AbstractUser):
    ROLES = [("senior", "Senior Citizen"), ("volunteer", "Volunteer"), ("admin", "Administrator")]
    VSTATUS = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    role = models.CharField(max_length=10, choices=ROLES, default="senior")
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    verification_status = models.CharField(max_length=10, choices=VSTATUS, default="pending")
    @property
    def approved(self): return self.verification_status == "approved"
    @property
    def wa_number(self):
        d = "".join(c for c in self.phone if c.isdigit())
        return d if len(d) > 10 else "91" + d

class SeniorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="senior_profile")
    age = models.PositiveIntegerField(null=True, blank=True)

class VolunteerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="volunteer_profile")
    occupation = models.CharField(max_length=100, blank=True)

class VerificationRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verifications")
    document = models.FileField(upload_to="verification/")  # served only via permission-checked view
    status = models.CharField(max_length=10, default="pending")
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)

class Category(models.Model):
    name = models.CharField(max_length=100)
    name_hi = models.CharField(max_length=100, blank=True)
    name_mr = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    def label(self, lang):
        return getattr(self, "name_" + lang, "") or self.name if lang != "en" else self.name
    def __str__(self): return self.name

class HelpRequest(models.Model):
    STATUS = [("pending","Pending"),("accepted","Accepted"),("in_progress","In Progress"),
              ("completed","Completed"),("cancelled","Cancelled")]
    senior = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requests")
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    description = models.TextField()
    required_date = models.DateField()
    preferred_time = models.TimeField()
    location = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    class Meta: ordering = ["-created"]
    @property
    def active_assignment(self):
        return self.assignments.filter(status__in=["accepted","in_progress"]).first()

class Assignment(models.Model):
    request = models.ForeignKey(HelpRequest, on_delete=models.CASCADE, related_name="assignments")
    volunteer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assignments")
    accepted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, default="accepted")  # accepted/in_progress/completed/withdrawn
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["request"],
            condition=Q(status__in=["accepted","in_progress"]), name="one_active_assignment_per_request")]

class Complaint(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="complaints")
    request = models.ForeignKey(HelpRequest, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField()
    status = models.CharField(max_length=10, default="open")
    admin_action = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)

class ActivityLog(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    detail = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created"]
