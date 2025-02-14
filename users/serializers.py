from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user CRUD operations"""

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'password', 'email']
        extra_kwargs = {'password': {'write_only': True}}  # Hide password in responses

    def create(self, validated_data):
        """Hash password before saving the user"""
        user = User(
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name'),
            username=validated_data.get('username'),
            email=validated_data.get('email'),
        )
        user.set_password(validated_data['password'])  # Hash password
        user.save()
        return user

    def update(self, instance, validated_data):
        """Hash password when updating"""
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])  # Hash password
        return super().update(instance, validated_data)


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        """Authenticate user"""
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid username or password")
        return user


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset"""
    username = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data
