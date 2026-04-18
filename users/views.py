from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from .models import CustomUser


class RegisterView(APIView):
    # This explicitly tells Django we are receiving files + text
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        # We grab whatever they typed into the first box
        login_id = request.data.get('username')
        password = request.data.get('password')

        # SMART LOGIC: If it has an '@', it's an email. Find the username attached to it!
        if '@' in str(login_id):
            try:
                user_obj = CustomUser.objects.get(email=login_id)
                login_id = user_obj.username  # Swap the email for the real username
            except CustomUser.DoesNotExist:
                pass  # If email doesn't exist, let it fail normally below

        user = authenticate(username=login_id, password=password)

        if user:
            # Safely grab the cloud URL if the picture exists
            try:
                profile_pic_url = user.profile_picture.url if user.profile_picture else None
            except ValueError:
                profile_pic_url = None

            return Response({
                "message": "Login successful!",
                "username": user.username,
                "role": user.role,
                "profile_picture": profile_pic_url,
                "trust_tier": user.trust_tier,
                "trust_score": user.trust_score
            }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


# --- SPRINT 2: ADMIN KYC VERIFICATION ENGINE ---

class PendingKYCView(APIView):
    def get(self, request):
        # Find everyone who is Unverified and NOT an admin
        pending_users = CustomUser.objects.filter(trust_tier='Unverified').exclude(role='admin')
        data = []

        for user in pending_users:
            # Safely extract cloud media URLs
            try:
                pfp_url = user.profile_picture.url if user.profile_picture else None
            except ValueError:
                pfp_url = None

            try:
                kyc_url = user.kyc_video.url if user.kyc_video else None
            except ValueError:
                kyc_url = None

            data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role.title(),
                'nid': user.nid_passport_number,
                'profile_picture': pfp_url,
                'kyc_video': kyc_url
            })

        return Response(data, status=status.HTTP_200_OK)


class ApproveKYCView(APIView):
    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            user.trust_tier = 'Verified'
            user.trust_score = 7.0  # Give them a trust boost for passing KYC!

            # THE AUTO-SHREDDER
            if user.kyc_video:
                user.kyc_video.delete(save=False)

            user.save()
            return Response({"message": f"{user.username} Approved!"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class DeclineKYCView(APIView):
    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            user.trust_tier = 'Rejected'

            # Shred the video even if they are rejected!
            if user.kyc_video:
                user.kyc_video.delete(save=False)

            user.save()
            return Response({"message": f"{user.username} Rejected!"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)