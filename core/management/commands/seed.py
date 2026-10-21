from django.core.management.base import BaseCommand
from core.models import *
CATS = [("Hospital / Doctor Visit","अस्पताल / डॉक्टर भेंट","रुग्णालय / डॉक्टर भेट"),("Grocery Shopping","किराना खरीदारी","किराणा खरेदी"),
("Daily Assistance","दैनिक सहायता","दैनंदिन मदत"),("Transportation","परिवहन","वाहतूक"),
("Government Office Assistance","सरकारी कार्यालय सहायता","सरकारी कार्यालय मदत"),("Companionship","साथ / संगति","सहवास"),("Other Assistance","अन्य सहायता","इतर मदत")]
class Command(BaseCommand):
    help = "Seed categories, admin and demo users (fake data only)"
    def handle(self, *a, **k):
        for n, h, m in CATS: Category.objects.get_or_create(name=n, defaults={"name_hi": h, "name_mr": m})
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "Admin@12345", role="admin", phone="9000000000", verification_status="approved")
        for u, r in (("senior_demo", "senior"), ("volunteer_demo", "volunteer")):
            if not User.objects.filter(username=u).exists():
                x = User.objects.create_user(u, password="Demo@12345", role=r, phone="9111111111", first_name=u.split("_")[0].title(), last_name="Demo", verification_status="approved")
                (SeniorProfile if r == "senior" else VolunteerProfile).objects.create(user=x)
        self.stdout.write("Seeded. admin / Admin@12345 ; senior_demo & volunteer_demo / Demo@12345")
