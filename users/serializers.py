import re
from rest_framework import serializers
from .models import CustomUser

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number']

    # --- UNIQUE EMAIL CHECK ---
    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    # --- UNIQUE NID CHECK ---
    def validate_nid_passport_number(self, value):
        # We also check if it's not empty, just in case they try to bypass it with blank spaces
        if value and CustomUser.objects.filter(nid_passport_number=value).exists():
            raise serializers.ValidationError("This NID/Passport number is already registered to another user.")
        return value

    # --- PASSWORD SECURITY LOGIC ---
    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def create(self, validated_data):
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', '')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user