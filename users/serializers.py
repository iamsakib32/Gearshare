import re
from rest_framework import serializers
from .models import CustomUser


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    # Temporary field just for checking the code, it won't save to the database
    master_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number', 'master_code']

    # --- UNIQUE EMAIL CHECK ---
    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    # --- UNIQUE NID CHECK ---
    def validate_nid_passport_number(self, value):
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

    # --- THE ADMIN BOUNCER ---
    def validate(self, data):
        # If they selected Admin, they MUST have the correct Master Code
        if data.get('role') == 'admin':
            if data.get('master_code') != 'VAULT_ADMIN_2026':
                raise serializers.ValidationError({"master_code": "Access Denied: Invalid Admin Clearance Code."})
        return data

    def create(self, validated_data):
        # Remove master_code so it doesn't try to save to the database model
        validated_data.pop('master_code', None)

        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', '')
        )

        # QA Auto-Upgrade: If they successfully registered as Admin, give them max trust instantly
        if user.role == 'admin':
            user.trust_tier = 'Platform Admin'
            user.trust_score = 10.0

        user.set_password(validated_data['password'])
        user.save()
        return user