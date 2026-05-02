from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path("", views.note_list, name="list"),
    path("notes/new/", views.note_create, name="create"),
    path("notes/trash/empty/", views.trash_empty, name="empty_trash"),
    path("notes/<int:pk>/", views.note_edit, name="edit"),
    path("notes/<int:pk>/autosave/", views.note_autosave, name="autosave"),
    path("notes/<int:pk>/<slug:action>/", views.note_action, name="action"),
]
