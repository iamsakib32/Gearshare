import re
from rest_framework import serializers
from .models import CustomUser
from .models import GearItem


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    # Temporary field just for checking the code, it won't save to the database
    master_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number', 'master_code', 'profile_picture',
                  'kyc_video']

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

    # --- THE ADMIN BOUNCER & KYC ENFORCER ---
    def validate(self, data):
        role = data.get('role', 'renter')

        # 1. Admin Verification
        if role == 'admin':
            if data.get('master_code') != 'VAULT_ADMIN_2026':
                raise serializers.ValidationError({"master_code": "Access Denied: Invalid Admin Clearance Code."})

        # 2. Renter/Owner Trust Verification
        else:
            if not data.get('nid_passport_number'):
                raise serializers.ValidationError({
                                                      "nid_passport_number": "Security Alert: NID/Passport is strictly required for Renters and Owners."})

        return data

    def create(self, validated_data):
        # Remove master_code so it doesn't try to save to the database model
        validated_data.pop('master_code', None)

        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', ''),

            # --- THE FIX: Tell Django to actually save the cloud media! ---
            profile_picture=validated_data.get('profile_picture'),
            kyc_video=validated_data.get('kyc_video')
        )

        # QA Auto-Upgrade: Admin gets permanent Verified status instantly
        if user.role == 'admin':
            user.trust_tier = 'Verified'
            user.trust_score = 10.0

        user.set_password(validated_data['password'])

        # The moment we call .save(), Django will automatically beam the files to Supabase S3!
        user.save()
        return user

class GearItemSerializer(serializers.ModelSerializer):
    # This automatically gets the owner's username instead of just their ID number
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = GearItem
        fields = ['id', 'title', 'description', 'price_per_day', 'condition', 'image', 'owner_username']