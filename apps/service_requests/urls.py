from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ServiceRequestViewSet, StatisticsView

router = SimpleRouter()
router.register("requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = router.urls + [
    path("statistics/", StatisticsView.as_view(), name="statistics"),
]