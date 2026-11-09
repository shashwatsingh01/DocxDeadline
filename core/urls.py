from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("overview/", views.dashboard, name="dashboard"),
    path("documents/", views.document_list, name="document_list"),
    path("documents/add/", views.document_create, name="document_create"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/edit/", views.document_edit, name="document_edit"),
    path("documents/<int:pk>/download/", views.document_download, name="document_download"),
    path("documents/<int:pk>/delete/", views.document_delete, name="document_delete"),
    path("deadlines/", views.deadline_list, name="deadline_list"),
    path("deadlines/add/", views.deadline_create, name="deadline_create"),
    path("deadlines/<int:pk>/", views.deadline_detail, name="deadline_detail"),
    path("deadlines/<int:pk>/edit/", views.deadline_edit, name="deadline_edit"),
    path("deadlines/<int:pk>/toggle/", views.deadline_toggle_complete, name="deadline_toggle_complete"),
    path("deadlines/<int:pk>/delete/", views.deadline_delete, name="deadline_delete"),
    path("applications/", views.application_list, name="application_list"),
    path("applications/add/", views.application_create, name="application_create"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
    path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),
    path("applications/<int:application_pk>/requirements/add/", views.requirement_create, name="requirement_create"),
    path("applications/<int:application_pk>/requirements/<int:pk>/delete/", views.requirement_delete, name="requirement_delete"),
    path("applications/<int:application_pk>/documents/attach/", views.application_document_attach, name="application_document_attach"),
    path("applications/<int:application_pk>/documents/<int:pk>/remove/", views.application_document_unlink, name="application_document_unlink"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/events/", views.calendar_events, name="calendar_events"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("activity/", views.activity_list, name="activity"),
    path("settings/", views.settings_view, name="settings"),
]
