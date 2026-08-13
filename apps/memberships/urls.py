from django.urls import path

from . import views


app_name = "memberships"


urlpatterns = [
    path(
        "",
        views.membership_list,
        name="list",
    ),
    path(
        "add/",
        views.membership_create,
        name="create",
    ),
]