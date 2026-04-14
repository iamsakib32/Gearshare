from rest_framework import serializers
from .models import CustomUser

class UserRegistrationSerializer(serializers.ModelSerializer):
    # Make password write-only, and force email to be required!
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True) # <--- ADD THIS LINE

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role', 'nid_passport_number']

    def create(self, validated_data):
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'], # <--- Make sure this reads the required email
            role=validated_data.get('role', 'renter'),
            nid_passport_number=validated_data.get('nid_passport_number', '')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user