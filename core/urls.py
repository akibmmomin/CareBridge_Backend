from django.urls import path
from . import views as v
urlpatterns = [
 # auth & profile
 path("auth/register/<str:role>/", v.register), path("auth/login/", v.login), path("auth/logout/", v.logout),
 path("auth/me/", v.me), path("auth/resubmit/", v.resubmit), path("profile/", v.profile),
 # shared
 path("categories/", v.categories), path("dashboard/", v.dashboard), path("report/", v.report),
 # requests
 path("requests/", v.my_requests), path("requests/available/", v.available), path("assignments/", v.my_assignments),
 path("requests/<int:pk>/", v.request_detail), path("requests/<int:pk>/accept/", v.accept),
 path("requests/<int:pk>/progress/<str:action>/", v.progress), path("requests/<int:pk>/cancel/", v.cancel_request),
 # administrator
 path("manage/dashboard/", v.admin_dashboard), path("manage/verifications/", v.admin_verifications),
 path("manage/verify/<int:pk>/<str:decision>/", v.admin_verify), path("manage/doc/<int:pk>/", v.verification_doc),
 path("manage/requests/", v.admin_requests), path("manage/categories/", v.admin_categories),
 path("manage/categories/<int:pk>/", v.admin_category_detail), path("manage/categories/<int:pk>/toggle/", v.admin_toggle_category),
 path("manage/users/", v.admin_users), path("manage/users/<int:pk>/toggle/", v.admin_toggle_user),
 path("manage/complaints/", v.admin_complaints), path("manage/activity/", v.admin_activity),
]
