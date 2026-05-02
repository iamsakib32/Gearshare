from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from .models import CustomUser, RoleSwitchRequest
from django.utils import timezone
from datetime import timedelta
from .models import GearItem
from .serializers import GearItemSerializer
from django.shortcuts import render, get_object_or_404
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

            # Check if there is an unread admin message, then clear it!
            role_msg = user.role_status_msg
            if role_msg:
                user.role_status_msg = ""
                user.save()

            return Response({
                "message": "Login successful!",
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "profile_picture": profile_pic_url,
                "trust_tier": user.trust_tier,
                "trust_score": user.trust_score,
                "can_switch_role": user.can_switch_role,
                "role_status_msg": role_msg
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
                'id': user.id, 'username': user.username, 'email': user.email,
                'role': user.role.title(), 'nid': user.nid_passport_number,
                'profile_picture': pfp_url, 'kyc_video': kyc_url
            })
        return Response(data, status=status.HTTP_200_OK)


class ApproveKYCView(APIView):
    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            user.trust_tier = 'Verified'
            user.trust_score = 7.0
            user.kyc_attempts = 0
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
            user.trust_tier = 'Unverified'
            user.save()
            return Response({"message": "KYC Resubmitted"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class GearListView(APIView):
    def get(self, request):
        items = GearItem.objects.filter(is_active=True).select_related('owner')
        serializer = GearItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def add_gear_page(request):
    return render(request, 'add_gear.html')


class AddGearAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        try:
            owner_id = request.data.get('owner_id')
            owner = CustomUser.objects.get(id=owner_id)
            new_item = GearItem.objects.create(
                owner=owner, title=request.data.get('title'),
                description=request.data.get('description'), price_per_day=request.data.get('price_per_day'),
                price_period=request.data.get('price_period', 'Day'), condition=request.data.get('condition', 'Good'),
            )
            if 'image' in request.FILES:
                new_item.image = request.FILES['image']
                new_item.save()
            return Response({"message": "Equipment added successfully!"}, status=status.HTTP_201_CREATED)
        except CustomUser.DoesNotExist:
            return Response({"error": "User authentication failed."}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def edit_gear_page(request, item_id):
    return render(request, 'edit_gear.html', {'item_id': item_id})


class GearDetailAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        serializer = GearItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        owner_id = request.data.get('owner_id')
        if str(item.owner.id) != str(owner_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        item.title = request.data.get('title', item.title)
        item.description = request.data.get('description', item.description)
        item.price_per_day = request.data.get('price_per_day', item.price_per_day)
        item.condition = request.data.get('condition', item.condition)
        if 'image' in request.FILES:
            item.image = request.FILES['image']
        item.save()
        return Response({"message": "Updated successfully!"}, status=status.HTTP_200_OK)

    def delete(self, request, item_id):
        item = get_object_or_404(GearItem, id=item_id)
        owner_id = request.query_params.get('owner_id')
        if str(item.owner.id) != str(owner_id):
            return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        item.delete()
        return Response({"message": "Deleted successfully!"}, status=status.HTTP_200_OK)


def gear_detail_page(request, item_id):
    return render(request, 'gear_detail.html', {'item_id': item_id})


def get_single_gear_api(request, item_id):
    try:
        item = GearItem.objects.get(id=item_id)
        try:
            image_url = item.image.url if item.image else None
        except ValueError:
            image_url = None
        data = {
            'id': item.id, 'title': item.title, 'description': item.description,
            'price_per_day': item.price_per_day, 'price_period': getattr(item, 'price_period', 'Day'),
            'condition': item.condition, 'owner_username': item.owner.username, 'image': image_url
        }
        return JsonResponse(data)
    except GearItem.DoesNotExist:
        return JsonResponse({'error': 'Equipment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# ROLE SWITCHER API ENDPOINTS


class SubmitRoleSwitchAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, user_id):
        user = get_object_or_404(CustomUser, id=user_id)
        requested_role = 'owner' if user.role == 'renter' else 'renter'

        product_name = request.data.get('product_name')
        product_image = request.FILES.get('product_image')

        if requested_role == 'owner' and (not product_name or not product_image):
            return Response({"error": "Product Name and Image are required."}, status=status.HTTP_400_BAD_REQUEST)

        if RoleSwitchRequest.objects.filter(user=user, status='Pending').exists():
            return Response({"error": "Application already pending."}, status=status.HTTP_400_BAD_REQUEST)

        RoleSwitchRequest.objects.create(
            user=user, current_role=user.role, requested_role=requested_role,
            product_name=product_name, product_image=product_image
        )
        return Response({"message": "Sent to Admin for review!"}, status=status.HTTP_200_OK)


class PendingRoleSwitchAPIView(APIView):
    def get(self, request):
        pending = RoleSwitchRequest.objects.filter(status='Pending')
        data = [{
            'id': r.id, 'user_id': r.user.id, 'username': r.user.username,
            'requested_role': r.requested_role.title(), 'product_name': r.product_name,
            'product_image': r.product_image.url if r.product_image else None
        } for r in pending]
        return Response(data, status=status.HTTP_200_OK)


class ApproveRoleSwitchAPIView(APIView):
    def post(self, request, request_id):
        req = get_object_or_404(RoleSwitchRequest, id=request_id)
        req.status = 'Approved'
        req.save()

        user = req.user
        user.can_switch_role = True
        user.role_status_msg = "APPROVED: Congratulations! Your application to switch roles was approved."
        user.save()



        return Response({"message": "Approved!"}, status=status.HTTP_200_OK)


class DeclineRoleSwitchAPIView(APIView):
    def post(self, request, request_id):
        req = get_object_or_404(RoleSwitchRequest, id=request_id)
        req.status = 'Rejected'
        req.save()

        user = req.user
        user.role_status_msg = "REJECTED: Sorry, your application to switch roles was declined."
        user.save()

        return Response({"message": "Declined."}, status=status.HTTP_200_OK)


class ToggleRoleAPIView(APIView):
    def post(self, request, user_id):
        user = get_object_or_404(CustomUser, id=user_id)
        if not user.can_switch_role:
            return Response({"error": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        new_role = 'owner' if user.role == 'renter' else 'renter'
        user.role = new_role
        user.save()
        return Response({"message": "Role Switched!", "new_role": new_role}, status=status.HTTP_200_OK)


class CheckRoleStatusAPIView(APIView):
    def get(self, request, user_id):
        user = get_object_or_404(CustomUser, id=user_id)
        msg = user.role_status_msg

        if msg:
            user.role_status_msg = ""
            user.save()

        return Response({
            "message": msg,
            "can_switch": user.can_switch_role
        }, status=status.HTTP_200_OK)