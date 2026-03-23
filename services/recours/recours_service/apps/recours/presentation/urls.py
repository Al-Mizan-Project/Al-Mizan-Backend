from django.urls import path


urlpatterns = [
    path("recours/", ...),
    path("recours/<int:recours_id>/", ...),
    path("recours/<int:recours_id>/instruire/", ...),
    path("recours/<int:recours_id>/decision/", ...),
    path("recours/<int:recours_id>/accepter/", ...),
    path("recours/<int:recours_id>/rejeter/", ...),
    path("recours/<int:recours_id>/cloturer/", ...),
]