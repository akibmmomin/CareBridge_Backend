"""JSON API views. Every endpoint returns JSON; the frontend (separate project) calls these with a Token header."""
from functools import wraps
from django.contrib.auth import authenticate
from django.db import transaction, IntegrityError
from django.db.models import ProtectedError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, authentication_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .forms import *
from .models import *

# ---------- helpers ----------
def err(msg, status=400, code=""): return Response({"detail": msg, "code": code}, status=status)
def form_err(form): return Response({"detail": "Please correct the errors.", "errors": {k: list(v) for k, v in form.errors.items()}}, status=400)
def log(user, action, detail=""): ActivityLog.objects.create(user=user, action=action, detail=str(detail)[:255])

def user_json(u):
    return {"id": u.id, "username": u.username, "first_name": u.first_name, "last_name": u.last_name, "full_name": u.get_full_name(),
            "email": u.email, "phone": u.phone, "address": u.address, "role": u.role,
            "verification_status": u.verification_status, "is_active": u.is_active}

def cat_json(c): return {"id": c.id, "name": c.name, "name_hi": c.name_hi, "name_mr": c.name_mr, "description": c.description, "active": c.active}

def req_json(r, admin=False):
    d = {"id": r.id, "category": cat_json(r.category), "description": r.description, "required_date": str(r.required_date),
         "preferred_time": r.preferred_time.strftime("%H:%M"), "location": r.location, "instructions": r.instructions,
         "created": r.created.isoformat(), "status": r.status}
    if admin:
        a = r.active_assignment
        d["senior"] = r.senior.get_full_name(); d["volunteer"] = a.volunteer.get_full_name() if a else ""
    return d

def role_required(role, need_approved=True):
    def deco(fn):
        @wraps(fn)
        def w(request, *a, **k):
            u = request.user
            if u.role != role: return err("Access denied.", 403, "forbidden")
            if need_approved and role != "admin" and not u.approved: return err("Account not approved.", 403, "not_approved")
            return fn(request, *a, **k)
        return w
    return deco

def _token_response(u, status=200):
    t, _ = Token.objects.get_or_create(user=u)
    return Response({"token": t.key, "user": user_json(u)}, status=status)

# ---------- auth ----------
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def register(request, role):
    if role not in ("senior", "volunteer"): raise Http404
    form = RegisterForm(request.data, request.FILES, role=role)
    if not form.is_valid(): return form_err(form)
    with transaction.atomic():
        u = form.save(commit=False); u.role = role; u.verification_status = "pending"; u.save()
        if role == "senior": SeniorProfile.objects.create(user=u, age=form.cleaned_data.get("age"))
        else: VolunteerProfile.objects.create(user=u, occupation=form.cleaned_data.get("occupation", ""))
        VerificationRecord.objects.create(user=u, document=form.cleaned_data["document"])
    log(u, "Registered", role)
    return _token_response(u, 201)

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    u = authenticate(request, username=request.data.get("username", ""), password=request.data.get("password", ""))
    if not u: return err("Invalid username or password.", 400, "bad_login")
    return _token_response(u)

@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({"detail": "Logged out."})

@api_view(["GET"])
def me(request):
    rec = request.user.verifications.order_by("-created").first()
    return Response({"user": user_json(request.user), "rejection_reason": rec.rejection_reason if rec else ""})

@api_view(["GET", "PUT"])
def profile(request):
    if request.method == "PUT":
        form = ProfileForm(request.data, instance=request.user)
        if not form.is_valid(): return form_err(form)
        form.save(); return Response({"detail": "Profile updated.", "user": user_json(request.user)})
    return Response({"user": user_json(request.user)})

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def resubmit(request):
    if request.user.verification_status != "rejected": return err("Invalid status change.")
    form = ResubmitForm(request.data, request.FILES)
    if not form.is_valid(): return form_err(form)
    VerificationRecord.objects.create(user=request.user, document=form.cleaned_data["document"])
    request.user.verification_status = "pending"; request.user.save(); log(request.user, "Document re-submitted")
    return Response({"detail": "Document re-submitted. Awaiting approval."})

# ---------- shared ----------
@api_view(["GET"])
def categories(request):
    return Response([cat_json(c) for c in Category.objects.filter(active=True)])

@api_view(["GET"])
def dashboard(request):
    u = request.user
    if u.role == "admin": return Response({"role": "admin"})
    if not u.approved: return err("Account not approved.", 403, "not_approved")
    if u.role == "senior":
        reqs = u.requests.select_related("category")
        return Response({"role": "senior", "requests": [req_json(r) for r in reqs[:5]],
                         "counts": {s: reqs.filter(status=s).count() for s, _ in HelpRequest.STATUS}})
    mine = u.assignments.filter(status__in=["accepted", "in_progress"]).select_related("request__category")
    return Response({"role": "volunteer", "open_count": HelpRequest.objects.filter(status="pending").count(),
                     "done": u.assignments.filter(status="completed").count(),
                     "mine": [{"status": a.status, "request": req_json(a.request)} for a in mine]})

# ---------- senior ----------
@api_view(["GET", "POST"])
@role_required("senior")
def my_requests(request):
    if request.method == "POST":
        form = RequestForm(request.data)
        if not form.is_valid(): return form_err(form)
        r = form.save(commit=False); r.senior = request.user; r.save(); log(request.user, "Request created", f"#{r.pk}")
        return Response({"detail": "Request submitted.", "request": req_json(r)}, status=201)
    return Response([req_json(r) for r in request.user.requests.select_related("category")])

@api_view(["POST"])
@role_required("senior")
def cancel_request(request, pk):
    r = get_object_or_404(HelpRequest, pk=pk, senior=request.user)
    if r.status not in ("pending", "accepted"): return err("This request can no longer be cancelled.")
    with transaction.atomic():
        r.assignments.filter(status__in=["accepted", "in_progress"]).update(status="withdrawn")
        r.status = "cancelled"; r.save(); log(request.user, "Request cancelled", f"#{pk}")
    return Response({"detail": "Request cancelled."})

# ---------- volunteer ----------
@api_view(["GET"])
@role_required("volunteer")
def available(request):
    return Response([req_json(r) for r in HelpRequest.objects.filter(status="pending").select_related("category")])

@api_view(["GET"])
@role_required("volunteer")
def my_assignments(request):
    items = request.user.assignments.select_related("request__category").order_by("-accepted_at")
    return Response([{"status": a.status, "request": req_json(a.request)} for a in items])

@api_view(["POST"])
@role_required("volunteer")
def accept(request, pk):
    try:
        with transaction.atomic():
            r = HelpRequest.objects.select_for_update().get(pk=pk)
            if r.status != "pending": return err("This request is no longer available.", 409)
            Assignment.objects.create(request=r, volunteer=request.user)
            r.status = "accepted"; r.save(); log(request.user, "Request accepted", f"#{pk}")
    except (IntegrityError, HelpRequest.DoesNotExist):
        return err("This request was just accepted by someone else.", 409)
    return Response({"detail": "Request accepted."})

@api_view(["POST"])
@role_required("volunteer")
def progress(request, pk, action):
    a = get_object_or_404(Assignment, request_id=pk, volunteer=request.user, status__in=["accepted", "in_progress"])
    r = a.request
    with transaction.atomic():
        if action == "start" and a.status == "accepted": a.status = r.status = "in_progress"
        elif action == "complete" and a.status == "in_progress":
            a.status = r.status = "completed"; a.completed_at = timezone.now()
        elif action == "withdraw": a.status = "withdrawn"; r.status = "pending"  # back to pool
        else: return err("Invalid status change.")
        a.save(); r.save(); log(request.user, f"Request {action}", f"#{pk}")
    return Response({"detail": "Status updated."})

# ---------- request detail (senior owner / assigned volunteer / admin) ----------
def _can_see(user, r):
    if user.role == "admin": return True
    if user.role == "senior": return r.senior_id == user.id and user.approved
    if user.role == "volunteer" and user.approved:
        return r.status == "pending" or r.assignments.filter(volunteer=user).exists()
    return False

@api_view(["GET"])
def request_detail(request, pk):
    r = get_object_or_404(HelpRequest, pk=pk)
    if not _can_see(request.user, r): return err("Access denied.", 403, "forbidden")
    a = r.active_assignment; contact = None
    # Contact exposed ONLY to the owning senior and the actively assigned volunteer (backend-enforced)
    if a and request.user.approved:
        c = a.volunteer if request.user.id == r.senior_id else (r.senior if request.user.id == a.volunteer_id else None)
        if c: contact = {"name": c.get_full_name(), "phone": c.phone, "wa_number": c.wa_number}
    d = req_json(r)
    d.update({"contact": contact, "is_owner": request.user.id == r.senior_id,
              "is_assignee": bool(a and a.volunteer_id == request.user.id), "assignment_status": a.status if a else None})
    return Response(d)

# ---------- complaints ----------
@api_view(["GET", "POST"])
def report(request):
    u = request.user
    if u.role == "admin" or not u.approved: return err("Access denied.", 403, "forbidden")
    if request.method == "POST":
        form = ComplaintForm(request.data, user=u)
        if not form.is_valid(): return form_err(form)
        c = form.save(commit=False); c.reporter = u; c.save(); log(u, "Complaint filed", f"#{c.pk}")
        return Response({"detail": "Report sent to administrator."}, status=201)
    form = ComplaintForm(user=u)   # list of requests this user can report about
    return Response([{"id": r.id, "category": cat_json(r.category), "required_date": str(r.required_date)}
                     for r in form.fields["request"].queryset.select_related("category")])

# ---------- administrator ----------
@api_view(["GET"])
@role_required("admin")
def admin_dashboard(request):
    return Response({"seniors": User.objects.filter(role="senior").count(), "volunteers": User.objects.filter(role="volunteer").count(),
        "pending_v": User.objects.filter(verification_status="pending").exclude(role="admin").count(),
        "counts": {s: HelpRequest.objects.filter(status=s).count() for s, _ in HelpRequest.STATUS},
        "open_c": Complaint.objects.filter(status="open").count()})

@api_view(["GET"])
@role_required("admin")
def admin_verifications(request):
    f = request.GET.get("s", "pending")
    users = User.objects.exclude(role="admin").filter(verification_status=f).prefetch_related("verifications")
    return Response([{**user_json(u), "documents": [{"id": v.id, "created": v.created.isoformat(), "status": v.status}
                      for v in u.verifications.all()]} for u in users])

@api_view(["POST"])
@role_required("admin")
def admin_verify(request, pk, decision):
    if decision not in ("approve", "reject"): raise Http404
    u = get_object_or_404(User, pk=pk); rec = u.verifications.order_by("-created").first()
    u.verification_status = "approved" if decision == "approve" else "rejected"; u.save()
    log(request.user, f"Verification {u.verification_status}", u.username)
    if rec:
        rec.status = u.verification_status; rec.reviewed_by = request.user; rec.reviewed_at = timezone.now()
        rec.rejection_reason = str(request.data.get("reason", ""))[:255] if decision == "reject" else ""; rec.save()
    return Response({"detail": "Verification " + u.verification_status + "."})

@api_view(["GET"])
@role_required("admin")
def verification_doc(request, pk):  # protected document download (admin only)
    rec = get_object_or_404(VerificationRecord, pk=pk)
    return FileResponse(rec.document.open("rb"))

@api_view(["GET"])
@role_required("admin")
def admin_requests(request):
    qs = HelpRequest.objects.select_related("senior", "category")
    if request.GET.get("s"): qs = qs.filter(status=request.GET["s"])
    return Response([req_json(r, admin=True) for r in qs])

@api_view(["GET", "POST"])
@role_required("admin")
def admin_categories(request):
    if request.method == "POST":
        form = CategoryForm(request.data)
        if not form.is_valid(): return form_err(form)
        c = form.save(); log(request.user, "Category added", c.name)
        return Response(cat_json(c), status=201)
    return Response([cat_json(c) for c in Category.objects.all()])

@api_view(["PUT", "DELETE"])
@role_required("admin")
def admin_category_detail(request, pk):
    c = get_object_or_404(Category, pk=pk)
    if request.method == "PUT":
        form = CategoryForm(request.data, instance=c)
        if not form.is_valid(): return form_err(form)
        form.save(); log(request.user, "Category edited", c.name); return Response(cat_json(c))
    try: c.delete(); log(request.user, "Category deleted", c.name)
    except ProtectedError: return err("Category is used by requests. Deactivate it instead.", 409)
    return Response({"detail": "Deleted."})

@api_view(["POST"])
@role_required("admin")
def admin_toggle_category(request, pk):
    c = get_object_or_404(Category, pk=pk); c.active = not c.active; c.save(); return Response(cat_json(c))

@api_view(["GET"])
@role_required("admin")
def admin_users(request):
    return Response([user_json(u) for u in User.objects.exclude(role="admin")])

@api_view(["POST"])
@role_required("admin")
def admin_toggle_user(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.role == "admin": return err("Access denied.", 403, "forbidden")
    u.is_active = not u.is_active; u.save()
    log(request.user, "Account " + ("activated" if u.is_active else "suspended"), u.username)
    return Response(user_json(u))

@api_view(["GET", "POST"])
@role_required("admin")
def admin_complaints(request):
    if request.method == "POST":
        c = get_object_or_404(Complaint, pk=request.data.get("id"))
        c.status = "resolved"; c.admin_action = str(request.data.get("action", ""))[:255]; c.save()
        log(request.user, "Complaint resolved", f"#{c.pk}")
        return Response({"detail": "Resolved."})
    return Response([{"id": c.id, "reporter": c.reporter.get_full_name(), "request": c.request_id, "description": c.description,
                      "status": c.status, "admin_action": c.admin_action, "created": c.created.isoformat()}
                     for c in Complaint.objects.select_related("reporter")])

@api_view(["GET"])
@role_required("admin")
def admin_activity(request):
    return Response([{"id": i.id, "user": i.user.username if i.user else "", "action": i.action, "detail": i.detail,
                      "created": i.created.isoformat()} for i in ActivityLog.objects.select_related("user")[:200]])
