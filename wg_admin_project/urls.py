from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from peers import views as peer_views
from commits import views as commit_views
from usage import views as usage_views
from integrations import views as integration_views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('django-admin/', admin.site.urls),
    path('dashboard/', peer_views.dashboard, name='dashboard'),
    path('users/', peer_views.user_list, name='user_list'),
    path('users/add/', peer_views.user_add, name='user_add'),
    path('users/<int:user_id>/', peer_views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', peer_views.user_edit, name='user_edit'),
    path('peers/add/<int:user_id>/', peer_views.peer_add, name='peer_add'),
    path('peers/<int:peer_id>/setup/', peer_views.peer_setup, name='peer_setup'),
    path('peers/<int:peer_id>/disable/', peer_views.peer_disable, name='peer_disable'),
    path('peers/<int:peer_id>/client-config/download/', peer_views.peer_client_config_download, name='peer_client_config_download'),
    path('commit/', commit_views.commit_config, name='commit_config'),
    path('usage/', usage_views.usage_dashboard, name='usage_dashboard'),
    path('settings/digitalocean/', integration_views.digitalocean_settings, name='digitalocean_settings'),
    path('settings/privacy/', integration_views.privacy_settings, name='privacy_settings'),
]
