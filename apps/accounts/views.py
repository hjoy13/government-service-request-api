from rest_framework import generics, permissions

from .serializers import RegisterSerializer
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"