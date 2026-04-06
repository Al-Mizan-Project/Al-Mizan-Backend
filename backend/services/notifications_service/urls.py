from django.urls import path
from .views import (
    NotificationListView,
    NotificationDetailView,
    UserNotificationsView,
    SendNotificationView,
    MarkNotificationReadView,
    MarkAllUserNotificationsReadView,
    MassSendNotificationsView
)

urlpatterns = [
    path('notifications', NotificationListView.as_view(), name='notifications-list'),
    path('notifications/<int:notification_id>', NotificationDetailView.as_view(), name='notification-detail'),
    path('users/<int:user_id>/notifications', UserNotificationsView.as_view(), name='user-notifications'),
    path('notifications/<int:notification_id>/envoyer', SendNotificationView.as_view(), name='notification-envoyer'),
    path('notifications/<int:notification_id>/marquer-lu', MarkNotificationReadView.as_view(), name='notification-marquer-lu'),
    path('users/<int:user_id>/notifications/marquer-tout-lu', MarkAllUserNotificationsReadView.as_view(), name='user-notifications-marquer-tout-lu'),
    path('notifications/envoi-masse', MassSendNotificationsView.as_view(), name='notifications-envoi-masse'),
]
