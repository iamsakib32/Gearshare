import re
from rest_framework import serializers
from .models import CustomUser, GearItem, GearGallery


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    master_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number', 'master_code', 'profile_picture',
                  'kyc_video']

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_nid_passport_number(self, value):
        if value and CustomUser.objects.filter(nid_passport_number=value).exists():
            raise serializers.ValidationError("This NID/Passport number is already registered to another user.")
        return value

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

    def validate(self, data):
        role = data.get('role', 'renter')
        if role == 'admin':
            if data.get('master_code') != 'VAULT_ADMIN_2026':
                raise serializers.ValidationError({"master_code": "Access Denied: Invalid Admin Clearance Code."})
        else:
            if not data.get('nid_passport_number'):
                raise serializers.ValidationError({
                    "nid_passport_number": "Security Alert: NID/Passport is strictly required for Renters and Owners."})
        return data

    def create(self, validated_data):
        validated_data.pop('master_code', None)

        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', ''),
            profile_picture=validated_data.get('profile_picture'),
            kyc_video=validated_data.get('kyc_video')
        )

        if user.role == 'admin':
            user.trust_tier = 'Verified'
            user.trust_score = 10.0

        user.set_password(validated_data['password'])
        user.save()
        return user


class GearGallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = GearGallery
        fields = ['id', 'image']


class GearItemSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    owner_trust_score = serializers.FloatField(source='owner.trust_score', read_only=True)
    owner_trust_tier = serializers.CharField(source='owner.trust_tier', read_only=True)
    gallery_images = GearGallerySerializer(many=True, read_only=True)

    class Meta:
        model = GearItem
        fields = '__all__'