from django.urls import include, path
from mvault_app import views

urlpatterns = [path("", include("mvault_app.urls")), path("health/", views.health, name="health")]
