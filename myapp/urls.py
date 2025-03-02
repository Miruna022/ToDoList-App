from django.urls import path
from . import views

urlpatterns = [
    path("", views.login, name = 'login'),
    path('upcoming/', views.upcoming, name='upcoming'),
    path('addtask/', views.addtask, name='addtask'),
    path('google/login/', views.google_login, name='google-login'),
    path('google/callback/', views.google_callback, name='google-callback'),
    path('google/event/delete/<str:event_id>/<str:calendar>/', views.event_delete, name='google-event-delete'),
]