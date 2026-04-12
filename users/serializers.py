from rest_framework import serializers
from .models import CustomUser

class UserRegistrationSerializer(serializers.ModelSerializer):
    # We make password write-only so it never gets sent back to the frontend accidentally
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number']

    def create(self, validated_data):
        # We create the user object but DON'T save it to the database yet
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', '')
        )
        # THIS IS THE MAGIC LINE: It automatically applies military-grade encryption to the password
        user.set_password(validated_data['password'])
        user.save() # Now we save it securely
        return user