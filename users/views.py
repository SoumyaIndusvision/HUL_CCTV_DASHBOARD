from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model

from .serializers import UserSerializer, UserLoginSerializer, PasswordResetSerializer

User = get_user_model()


class UserAPIView(viewsets.ViewSet):
    """
    API for managing Users (CRUD operations).
    """

    @swagger_auto_schema(
        operation_summary="List all users",
        responses={200: UserSerializer(many=True)}
    )
    def list(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response({"results": serializer.data, "status": status.HTTP_200_OK})

    @swagger_auto_schema(
        operation_summary="Retrieve a specific user",
        responses={200: UserSerializer()}
    )
    def retrieve(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            serializer = UserSerializer(user)
            return Response({"results": serializer.data, "status": status.HTTP_200_OK})
        except User.DoesNotExist:
            return Response({"message": "User not found", "status": status.HTTP_404_NOT_FOUND})

    @swagger_auto_schema(
        operation_summary="Create a new user",
        request_body=UserSerializer,
        responses={201: "User created", 400: "Bad Request"}
    )
    def create(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created", "status": status.HTTP_201_CREATED})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Update an existing user",
        request_body=UserSerializer,
        responses={200: "User updated", 400: "Bad Request"}
    )
    def update(self, request, pk=None):
        user = User.objects.get(pk=pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User updated", "status": status.HTTP_200_OK})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Delete a user",
        responses={204: "User deleted", 404: "Not Found"}
    )
    def destroy(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            user.delete()
            return Response({"message": "User deleted", "status": status.HTTP_204_NO_CONTENT})
        except User.DoesNotExist:
            return Response({"message": "User not found", "status": status.HTTP_404_NOT_FOUND})


class LoginAPIView(APIView):
    """
    API for user authentication.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="User login",
        request_body=UserLoginSerializer,
        responses={200: "Login successful", 400: "Invalid credentials"}
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response({"message": "Login successful", "status": status.HTTP_200_OK})
        return Response({"message": "Invalid username or password", "status": status.HTTP_400_BAD_REQUEST}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetAPIView(APIView):
    """
    API for resetting user passwords using username instead of email.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Reset user password using username",
        request_body=PasswordResetSerializer,
        responses={200: "Password reset successful", 400: "Invalid request"}
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            new_password = serializer.validated_data['new_password']

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"message": "User not found", "status": status.HTTP_404_NOT_FOUND})

            user.set_password(new_password)
            user.save()
            return Response({"message": "Password reset successful", "status": status.HTTP_200_OK})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
