from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from .models import CustomUser  # <--- Add this import


# (Keep your RegisterView exactly how it is)
class RegisterView(APIView):
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
            return Response({
                "message": "Login successful!",
                "username": user.username,
                "role": user.role
            }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)