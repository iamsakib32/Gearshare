from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from .models import CustomUser
from django.utils import timezone
from datetime import timedelta
from .models import GearItem
from .serializers import GearItemSerializer
from django.shortcuts import render,get_object_or_404
from django.http import JsonResponse


class RegisterView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        login_id = request.data.get('username')
        password = request.data.get('password')

        if '@' in str(login_id):
            try:
                user_obj = CustomUser.objects.get(email=login_id)
                login_id = user_obj.username
            except CustomUser.DoesNotExist:
                pass

        user = authenticate(username=login_id, password=password)

        if user:
            # --- THE BAN BOUNCER ---
            if user.trust_tier == 'Suspended' and user.suspension_date:
                if timezone.now() > user.suspension_date + timedelta(days=3):
                    return Response({"error": "Account Permanently Locked"}, status=status.HTTP_403_FORBIDDEN)

            try:
                profile_pic_url = user.profile_picture.url if user.profile_picture else None
            except ValueError:
                profile_pic_url = None

            return Response({
                "message": "Login successful!",
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "profile_picture": profile_pic_url,
                "trust_tier": user.trust_tier,
                "trust_score": user.trust_score
            }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


# --- ADMIN & LIFECYCLE ENGINE ---

class PendingKYCView(APIView):
    def get(self, request):
        pending_users = CustomUser.objects.filter(trust_tier='Unverified').exclude(role='admin')
        data = []
        for user in pending_users:
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
            user.trust_score = 7.0
            user.kyc_attempts = 0  # Reset strikes on approval!

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

            if user.kyc_video:
                user.kyc_video.delete(save=False)

            # THE STRIKE SYSTEM
            if user.kyc_attempts == 0:
                user.trust_tier = 'Rejected'
                user.kyc_attempts = 1
            else:
                user.trust_tier = 'Suspended'
                user.suspension_date = timezone.now()

            user.save()
            return Response({"message": f"{user.username} Rejected!"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class ResubmitKYCView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            user.nid_passport_number = request.data.get('nid_passport_number', user.nid_passport_number)

            if 'kyc_video' in request.FILES:
                user.kyc_video = request.FILES['kyc_video']

            user.trust_tier = 'Unverified'  # Send back to queue
            user.save()
            return Response({"message": "KYC Resubmitted"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

class GearListView(APIView):
    def get(self, request):
        # Grab all gear that is currently active/available
        items = GearItem.objects.filter(is_active=True).select_related('owner')
        # Convert it to JSON using the serializer we just made
        serializer = GearItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 1. This simply loads the HTML page when you go to /add-gear/
def add_gear_page(request):
    return render(request, 'add_gear.html')


# 2. This is the API that receives the form data and saves it
class AddGearAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)  # Allows uploading images

    def post(self, request):
        try:
            # Get the user ID sent from the frontend JavaScript
            owner_id = request.data.get('owner_id')
            owner = CustomUser.objects.get(id=owner_id)

            # Create the new item in the database
            new_item = GearItem.objects.create(
                owner=owner,
                title=request.data.get('title'),
                description=request.data.get('description'),
                price_per_day=request.data.get('price_per_day'),
                price_period=request.data.get('price_period', 'Day'),
                condition=request.data.get('condition', 'Good'),
            )

            # If they uploaded a picture, save it to the item
            if 'image' in request.FILES:
                new_item.image = request.FILES['image']
                new_item.save()

            return Response({"message": "Equipment added successfully!"}, status=status.HTTP_201_CREATED)

        except CustomUser.DoesNotExist:
            return Response({"error": "User authentication failed."}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# 1. This loads the HTML page for editing
def edit_gear_page(request, item_id): # <-- Make sure item_id is here!
    # Make sure you are passing the dictionary {'item_id': item_id} at the end!
    return render(request, 'edit_gear.html', {'item_id': item_id})


# 2. This API handles fetching, updating, and deleting a specific item
class GearDetailAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    # GET: Fetch single item data to pre-fill the edit form
    def get(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        serializer = GearItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # PUT: Save the updated edits
    def put(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        owner_id = request.data.get('owner_id')

        # SECURITY CHECK: Only the owner can edit this!
        if str(item.owner.id) != str(owner_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        item.title = request.data.get('title', item.title)
        item.description = request.data.get('description', item.description)
        item.price_per_day = request.data.get('price_per_day', item.price_per_day)
        item.condition = request.data.get('condition', item.condition)

        # Only update image if a new one was uploaded
        if 'image' in request.FILES:
            item.image = request.FILES['image']

        item.save()
        return Response({"message": "Updated successfully!"}, status=status.HTTP_200_OK)

    # DELETE: Remove the item
    def delete(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        # FIX: Use query_params to successfully grab the ID from the JavaScript fetch URL
        owner_id = request.query_params.get('owner_id')

        # SECURITY CHECK
        if str(item.owner.id) != str(owner_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        item.delete()
        return Response({"message": "Deleted successfully!"}, status=status.HTTP_200_OK)

def gear_detail_page(request, item_id):
    return render(request, 'gear_detail.html', {'item_id': item_id})


def get_single_gear_api(request, item_id):
    try:
        # Find the specific item
        item = GearItem.objects.get(id=item_id)

        # Safely get the image URL
        try:
            image_url = item.image.url if item.image else None
        except ValueError:
            image_url = None

        # Package the data
        data = {
            'id': item.id,
            'title': item.title,
            'description': item.description,
            'price_per_day': item.price_per_day,
            'price_period': getattr(item, 'price_period', 'Day'),
            'condition': item.condition,
            'owner_username': item.owner.username,
            'image': image_url
        }
        return JsonResponse(data)

    except GearItem.DoesNotExist:
        return JsonResponse({'error': 'Equipment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)