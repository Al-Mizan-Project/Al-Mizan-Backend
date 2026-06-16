from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Notification
from .serializers import NotificationSerializer

class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})

class ReadyView(APIView):
    def get(self, request):
        return Response({"status": "ready"})


class NotificationListView(APIView):
    """
    GET  /notifications - Récupérer toutes les notifications
    POST /notifications - Créer une notification
    """
    def get(self, request):
        notifications = Notification.objects.all()
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = NotificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NotificationDetailView(APIView):
    """
    GET    /notifications/{notification_id} - Récupérer les détails d'une notification
    PATCH  /notifications/{notification_id} - Modifier partiellement une notification
    DELETE /notifications/{notification_id} - Supprimer une notification
    """
    def get_object(self, notification_id):
        try:
            return Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return None

    def get(self, request, notification_id):
        notification = self.get_object(notification_id)
        if not notification:
            return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)

    def patch(self, request, notification_id):
        notification = self.get_object(notification_id)
        if not notification:
            return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        serializer = NotificationSerializer(notification, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, notification_id):
        notification = self.get_object(notification_id)
        if not notification:
            return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserNotificationsView(APIView):
    """
    GET /users/{user_id}/notifications - Lister les notifications d'un utilisateur spécifique
    """
    def get(self, request, user_id):
        notifications = Notification.objects.filter(utilisateur_id=user_id).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class MyNotificationsView(APIView):
    """
    GET /notifications/me - Lister les notifications de l'utilisateur connecte
    """
    def get(self, request):
        user_id = getattr(request.user, "pk", None)
        if not user_id:
            return Response({"error": "Authentification requise"}, status=status.HTTP_401_UNAUTHORIZED)

        notifications = Notification.objects.filter(utilisateur_id=user_id).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class SendNotificationView(APIView):
    """
    POST /notifications/{notification_id}/envoyer - Marquer une notification comme envoyée
    """
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        
        if notification.statut == "envoyée":
            return Response({"message": "Cette notification a déjà été envoyée"}, status=status.HTTP_400_BAD_REQUEST)

        notification.statut = "envoyée"
        notification.sent_at = timezone.now()
        notification.save()
        
        return Response({"message": "Notification envoyée avec succès", "sent_at": notification.sent_at})


class MarkNotificationReadView(APIView):
    """
    POST /notifications/{notification_id}/marquer-lu - Marquer une notification comme lue
    """
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        
        if notification.read_at is not None:
            return Response({"message": "Cette notification est déjà marquée comme lue"}, status=status.HTTP_400_BAD_REQUEST)

        notification.statut = "lue"
        notification.read_at = timezone.now()
        notification.save()
        
        return Response({"message": "Notification marquée comme lue", "read_at": notification.read_at})


class MarkAllUserNotificationsReadView(APIView):
    """
    POST /users/{user_id}/notifications/marquer-tout-lu - Marquer toutes les notifications d'un utilisateur comme lues
    """
    def post(self, request, user_id):
        notifications_to_update = Notification.objects.filter(utilisateur_id=user_id, read_at__isnull=True)
        count = notifications_to_update.count()
        
        if count == 0:
            return Response({"message": "Aucune notification à marquer comme lue"}, status=status.HTTP_200_OK)

        now = timezone.now()
        notifications_to_update.update(statut="lue", read_at=now)
        
        return Response({"message": f"{count} notifications marquées comme lues"})


class MarkAllMyNotificationsReadView(APIView):
    """
    POST /notifications/me/marquer-tout-lu - Marquer mes notifications comme lues
    """
    def post(self, request):
        user_id = getattr(request.user, "pk", None)
        if not user_id:
            return Response({"error": "Authentification requise"}, status=status.HTTP_401_UNAUTHORIZED)

        notifications_to_update = Notification.objects.filter(utilisateur_id=user_id, read_at__isnull=True)
        count = notifications_to_update.count()

        if count == 0:
            return Response({"message": "Aucune notification a marquer comme lue"}, status=status.HTTP_200_OK)

        now = timezone.now()
        notifications_to_update.update(statut="lue", read_at=now)

        return Response({"message": f"{count} notifications marquees comme lues"})


class MassSendNotificationsView(APIView):
    """
    POST /notifications/envoi-masse - Envoi de notifications en masse
    Corps attendu:
    {
        "notifications": [
            {
                "utilisateur_id": 1,
                "type_notification": "alerte",
                "titre": "Nouveau document",
                "message": "...",
                "priorite": "haute",
                "categorie": "document",
                "entite_liee_type": "contrat",
                "entite_liee_id": 42
            },
            ...
        ]
    }
    """
    def post(self, request):
        notifications_data = request.data.get("notifications", [])
        if not isinstance(notifications_data, list):
            return Response({"error": "La charge utile 'notifications' doit être une liste"}, status=status.HTTP_400_BAD_REQUEST)
        
        created_notifications = []
        errors = []
        now = timezone.now()

        for idx, item in enumerate(notifications_data):
            # Assigner statut envoyé et date d'envoi pour l'envoi en masse
            item["statut"] = "envoyée"
            
            serializer = NotificationSerializer(data=item)
            if serializer.is_valid():
                obj = serializer.save(sent_at=now)
                created_notifications.append(serializer.data)
            else:
                errors.append({"index": idx, "errors": serializer.errors})

        response_data = {
            "created": len(created_notifications),
            "errors": errors
        }
        
        if errors and not created_notifications:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        elif errors:
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(response_data, status=status.HTTP_201_CREATED)
