from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.schedule, name='schedule'),
    path('convention/<int:pk>/', views.convention_detail, name='convention_detail'),
    path('convention/create/', views.convention_create, name='convention_create'),
    path('convention/<int:pk>/edit/', views.convention_edit, name='convention_edit'),
    path('panel/create/<int:day_pk>/', views.panel_create, name='panel_create'),
    path('panel/<int:pk>/edit/', views.panel_edit, name='panel_edit'),
    path('panel/<int:pk>/delete/', views.panel_delete, name='panel_delete'),
    path('panel/<int:pk>/calendar/', views.panel_calendar, name='panel_calendar'),
    path('panel/<int:pk>/toggle-cancelled/', views.toggle_cancelled, name='toggle_cancelled'),
    path('logout/', views.logout_view, name='logout'),
    path('login/', views.login_view, name='login'),
    path('convention/<int:pk>/delete/', views.convention_delete, name='convention_delete'),
    path('add_panel_host_ajax/', views.add_panel_host_ajax, name='add_panel_host_ajax'),
    path('add_tag_ajax/', views.add_tag_ajax, name='add_tag_ajax'),
    path('panel/<int:pk>/details/', views.panel_detail_modal_view, name='panel_detail_modal_view'),
    path('tag/<str:name>/edit/', views.tag_edit, name='tag_edit'),
    path('host/<int:pk>/edit/', views.host_edit, name='host_edit'),
    path('ajax/hosts/delete/<int:pk>/', views.delete_host_ajax, name='delete_host_ajax'),
    path('ajax/tags/<int:pk>/details/', views.get_tag_details_ajax, name='get_tag_details_ajax'),
    path('ajax/hosts/<int:pk>/details/', views.get_host_details_ajax, name='get_host_details_ajax'),
    path('ajax/rooms/save/', views.save_room_ajax, name='save_room_ajax'),
    path('ajax/rooms/delete/<int:pk>/', views.delete_room_ajax, name='delete_room_ajax'),
    path('ajax/tags/delete/<int:pk>/', views.delete_tag_ajax, name='delete_tag_ajax'),
    path('ajax/rooms/<int:pk>/details/', views.get_room_details_ajax, name='get_room_details_ajax'),
    path('ajax/hosts/all/', views.get_all_hosts_ajax, name='get_all_hosts_ajax'),
    path('ajax/rooms/all/', views.get_all_rooms_ajax, name='get_all_rooms_ajax'),
    path('ajax/tags/all/', views.get_all_tags_ajax, name='get_all_tags_ajax'),
    path('ajax/tags/reorder/<int:panel_id>/', views.reorder_tags_ajax, name='reorder_tags_ajax'),
    path('ajax/hosts/reorder/<int:panel_id>/', views.reorder_hosts_ajax, name='reorder_hosts_ajax'),
] 