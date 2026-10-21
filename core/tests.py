from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import *

def client(token=None):
    c = APIClient()
    if token: c.credentials(HTTP_AUTHORIZATION="Token " + token)
    return c

class Base(TestCase):
    def setUp(self): call_command("seed", verbosity=0)
    def login(self, name, pw="Pass@12345"):
        r = APIClient().post("/api/auth/login/", {"username": name, "password": pw}, format="json")
        self.assertEqual(r.status_code, 200); return client(r.data["token"])
    def mk(self, name, role, status="approved"):
        return User.objects.create_user(name, password="Pass@12345", role=role, phone="9876543210",
                                        first_name=name, last_name="T", verification_status=status)
    def admin(self): return self.login("admin", "Admin@12345")
    def req(self, senior):
        return HelpRequest.objects.create(senior=senior, category=Category.objects.first(), description="d",
            required_date=date.today() + timedelta(days=1), preferred_time="10:00", location="Daund")

class Flow(Base):
    def reg(self, role, name):
        r = APIClient().post(f"/api/auth/register/{role}/", {"username": name, "first_name": "A", "last_name": "B", "email": "a@b.com",
            "phone": "9876543210", "address": "Pune", "password1": "Str0ng!Pass99", "password2": "Str0ng!Pass99",
            "document": SimpleUploadedFile("id.pdf", b"%PDF-1"), "age": 70, "occupation": "x"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data); return client(r.data["token"])
    def test_full_flow(self):
        s, v, other = self.reg("senior", "sen1"), self.reg("volunteer", "vol1"), self.reg("volunteer", "vol2")
        self.assertEqual(User.objects.get(username="sen1").verification_status, "pending")
        cat = Category.objects.first()
        data = {"category": cat.pk, "description": "Need help", "required_date": str(date.today() + timedelta(days=1)),
                "preferred_time": "10:00", "location": "Daund"}
        r = s.post("/api/requests/", data, format="json"); self.assertEqual((r.status_code, r.data["code"]), (403, "not_approved"))
        self.assertEqual(v.get("/api/requests/available/").status_code, 403)
        ad = self.admin()
        for n in ("sen1", "vol1"): self.assertEqual(ad.post(f"/api/manage/verify/{User.objects.get(username=n).pk}/approve/").status_code, 200)
        self.assertEqual(s.get("/api/manage/dashboard/").status_code, 403)
        self.assertEqual(s.post("/api/requests/", data, format="json").status_code, 201); r = HelpRequest.objects.get()
        self.assertEqual(other.post(f"/api/requests/{r.pk}/accept/").status_code, 403)  # unverified volunteer
        r.refresh_from_db(); self.assertEqual(r.status, "pending")
        self.assertIsNone(v.get(f"/api/requests/{r.pk}/").data["contact"])  # no phone before acceptance
        self.assertEqual(v.post(f"/api/requests/{r.pk}/accept/").status_code, 200)
        self.assertEqual(v.get(f"/api/requests/{r.pk}/").data["contact"]["wa_number"], "919876543210")
        self.assertEqual(s.get(f"/api/requests/{r.pk}/").data["contact"]["phone"], "9876543210")
        self.assertEqual(other.get(f"/api/requests/{r.pk}/").status_code, 403)
        self.assertEqual(v.post(f"/api/requests/{r.pk}/progress/complete/").status_code, 400)  # invalid jump
        v.post(f"/api/requests/{r.pk}/progress/start/"); v.post(f"/api/requests/{r.pk}/progress/complete/")
        r.refresh_from_db(); self.assertEqual(r.status, "completed")
        self.assertEqual(s.get("/api/dashboard/").data["counts"]["completed"], 1)

class MoreTests(Base):
    def test_invalid_login_and_no_token(self):
        r = APIClient().post("/api/auth/login/", {"username": "x", "password": "y"}, format="json"); self.assertEqual(r.status_code, 400)
        self.assertEqual(APIClient().get("/api/dashboard/").status_code, 401)
    def test_logout_invalidates_token(self):
        self.mk("s", "senior"); c = self.login("s"); c.post("/api/auth/logout/"); self.assertEqual(c.get("/api/auth/me/").status_code, 401)
    def test_role_blocking(self):
        self.mk("s", "senior"); self.mk("v", "volunteer")
        self.assertEqual(self.login("s").get("/api/requests/available/").status_code, 403)
        self.assertEqual(self.login("v").get("/api/requests/").status_code, 403)
        self.assertEqual(self.login("v").get("/api/manage/verifications/").status_code, 403)
    def test_required_and_past_date(self):
        self.mk("s", "senior"); c = self.login("s")
        self.assertEqual(c.post("/api/requests/", {"description": "x"}, format="json").status_code, 400)
        r = c.post("/api/requests/", {"category": Category.objects.first().pk, "description": "x", "required_date": "2020-01-01",
                                      "preferred_time": "10:00", "location": "x"}, format="json")
        self.assertEqual(r.status_code, 400); self.assertIn("required_date", r.data["errors"]); self.assertEqual(HelpRequest.objects.count(), 0)
    def test_double_accept_prevented(self):
        s = self.mk("s", "senior"); self.mk("v1", "volunteer"); self.mk("v2", "volunteer"); r = self.req(s)
        self.assertEqual(self.login("v1").post(f"/api/requests/{r.pk}/accept/").status_code, 200)
        self.assertEqual(self.login("v2").post(f"/api/requests/{r.pk}/accept/").status_code, 409)
        self.assertEqual(Assignment.objects.filter(request=r, status__in=["accepted", "in_progress"]).count(), 1)
    def test_contact_hidden_from_unrelated(self):
        s = self.mk("s", "senior"); self.mk("v1", "volunteer"); self.mk("v2", "volunteer"); self.mk("s2", "senior"); r = self.req(s)
        self.login("v1").post(f"/api/requests/{r.pk}/accept/")
        self.assertEqual(self.login("v2").get(f"/api/requests/{r.pk}/").status_code, 403)
        self.assertEqual(self.login("s2").get(f"/api/requests/{r.pk}/").status_code, 403)
    def test_withdraw_and_cancel(self):
        s = self.mk("s", "senior"); self.mk("s2", "senior"); self.mk("v1", "volunteer"); r = self.req(s); c = self.login("v1")
        c.post(f"/api/requests/{r.pk}/accept/"); c.post(f"/api/requests/{r.pk}/progress/withdraw/")
        r.refresh_from_db(); self.assertEqual(r.status, "pending")
        self.assertEqual(self.login("s2").post(f"/api/requests/{r.pk}/cancel/").status_code, 404)
        self.assertEqual(self.login("s").post(f"/api/requests/{r.pk}/cancel/").status_code, 200)
        r.refresh_from_db(); self.assertEqual(r.status, "cancelled")
    def test_reject_then_resubmit(self):
        u = self.mk("s", "senior", "pending"); VerificationRecord.objects.create(user=u, document="x.pdf")
        self.admin().post(f"/api/manage/verify/{u.pk}/reject/", {"reason": "Blurry"}, format="json")
        u.refresh_from_db(); self.assertEqual(u.verification_status, "rejected")
        c = self.login("s"); self.assertEqual(c.get("/api/auth/me/").data["rejection_reason"], "Blurry")
        c.post("/api/auth/resubmit/", {"document": SimpleUploadedFile("id2.pdf", b"%PDF-1")}, format="multipart")
        u.refresh_from_db(); self.assertEqual(u.verification_status, "pending")
    def test_verification_doc_admin_only(self):
        u = self.mk("s", "senior", "pending"); rec = VerificationRecord.objects.create(user=u, document=SimpleUploadedFile("a.pdf", b"x"))
        self.assertEqual(self.login("s").get(f"/api/manage/doc/{rec.pk}/").status_code, 403)
        self.assertEqual(self.admin().get(f"/api/manage/doc/{rec.pk}/").status_code, 200)
    def test_complaints(self):
        s = self.mk("s", "senior"); self.mk("v", "volunteer"); r = self.req(s)
        self.login("v").post(f"/api/requests/{r.pk}/accept/")
        self.assertEqual(self.login("v").post("/api/report/", {"description": "Problem", "request": r.pk}, format="json").status_code, 201)
        self.assertEqual(self.login("s").post("/api/report/", {"description": "Another"}, format="json").status_code, 201)
        ad = self.admin(); items = ad.get("/api/manage/complaints/").data; self.assertEqual(len(items), 2)
        ad.post("/api/manage/complaints/", {"id": items[0]["id"], "action": "Warned"}, format="json")
        self.assertEqual(Complaint.objects.filter(status="resolved").count(), 1)
    def test_category_crud(self):
        ad = self.admin(); c = Category.objects.create(name="Temp")
        r = ad.put(f"/api/manage/categories/{c.pk}/", {"name": "Temp2", "active": True}, format="json"); self.assertEqual(r.status_code, 200)
        c.refresh_from_db(); self.assertEqual(c.name, "Temp2")
        ad.post(f"/api/manage/categories/{c.pk}/toggle/")
        s = self.mk("s", "senior"); self.assertNotIn("Temp2", [x["name"] for x in self.login("s").get("/api/categories/").data])
        self.assertEqual(ad.delete(f"/api/manage/categories/{c.pk}/").status_code, 200)
        used = Category.objects.first(); self.req(s)
        self.assertEqual(ad.delete(f"/api/manage/categories/{used.pk}/").status_code, 409)
    def test_suspend_user_blocks_login(self):
        u = self.mk("s", "senior"); self.admin().post(f"/api/manage/users/{u.pk}/toggle/")
        self.assertEqual(APIClient().post("/api/auth/login/", {"username": "s", "password": "Pass@12345"}, format="json").status_code, 400)
    def test_activity_log_and_profile(self):
        s = self.mk("s", "senior"); c = self.login("s")
        c.post("/api/requests/", {"category": Category.objects.first().pk, "description": "x", "required_date": str(date.today() + timedelta(days=1)),
                                  "preferred_time": "10:00", "location": "x"}, format="json")
        self.assertTrue(any(i["action"] == "Request created" for i in self.admin().get("/api/manage/activity/").data))
        r = c.put("/api/profile/", {"first_name": "New", "last_name": "N", "email": "n@x.com", "phone": "9999999999", "address": "Z"}, format="json")
        self.assertEqual(r.data["user"]["first_name"], "New")
