from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from .models import CustomUser, RoleSwitchRequest, GearItem, GearGallery, RentalRequest, ChatMessage
from django.utils import timezone
from datetime import timedelta
from .serializers import GearItemSerializer
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import localtime
from urllib.parse import urlencode
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from decimal import Decimal, InvalidOperation
from django.db.models import Q
import random, requests
from django.core.mail import send_mail
from django.conf import settings


class RegisterView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


def get_user_tier_level(tier_string):
    tier_mapping = {
        'Suspended': 0,
        'Rejected': 1,
        'Unverified': 1,
        'Verified': 2,
    }
    return tier_mapping.get(tier_string, 1)


class GearListView(APIView):
    def get(self, request):
        user_id = request.query_params.get('user_id')

        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                user_clearance = user.trust_score
                items = GearItem.objects.filter(
                    is_active=True,
                    min_trust_tier__lte=user_clearance
                ).select_related('owner')
            except CustomUser.DoesNotExist:
                # Invalid user_id — fall back to showing everything
                items = GearItem.objects.filter(is_active=True).select_related('owner')
        else:
            # Logged-out users see all active listings — trust filtering only applies when renting
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

            is_negotiable_str = str(request.data.get('is_negotiable', 'true')).lower()
            is_negotiable = True if is_negotiable_str == 'true' else False

            new_item = GearItem.objects.create(
                owner=owner,
                title=request.data.get('title'),
                description=request.data.get('description'),
                price_per_day=request.data.get('price_per_day'),
                price_period=request.data.get('price_period', 'Day'),
                condition=request.data.get('condition', 'Good'),
                category=request.data.get('category', 'Other'),
                location=request.data.get('location', ''),
                area=request.data.get('area', ''),
                replacement_value=request.data.get('replacement_value') or 0.00,
                min_rental_duration=request.data.get('min_rental_duration', '1 day'),
                available_days=request.data.get('available_days', 'S,M,T,W,Th,F,Sa'),
                delivery_option=request.data.get('delivery_option', 'Pickup only'),
                pickup_location=request.data.get('pickup_location', ''),
                cancellation_policy=request.data.get('cancellation_policy', 'flexible'),
                is_negotiable=is_negotiable
            )

            if 'image' in request.FILES:
                new_item.image = request.FILES['image']

            new_item.save()

            extra_images = request.FILES.getlist('extra_images')
            for img in extra_images:
                GearGallery.objects.create(gear=new_item, image=img)

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
        item.price_period = request.data.get('price_period', item.price_period)
        item.condition = request.data.get('condition', item.condition)
        item.category = request.data.get('category', getattr(item, 'category', 'Other'))
        item.location = request.data.get('location', item.location)
        item.area = request.data.get('area', item.area)
        item.replacement_value = request.data.get('replacement_value', getattr(item, 'replacement_value', 0.00)) or 0.00
        item.min_rental_duration = request.data.get('min_rental_duration', getattr(item, 'min_rental_duration', '1 day'))
        item.available_days = request.data.get('available_days', getattr(item, 'available_days', 'S,M,T,W,Th,F,Sa'))
        item.delivery_option = request.data.get('delivery_option', getattr(item, 'delivery_option', 'Pickup only'))
        item.pickup_location = request.data.get('pickup_location', getattr(item, 'pickup_location', ''))
        item.cancellation_policy = request.data.get('cancellation_policy', getattr(item, 'cancellation_policy', 'flexible'))

        if 'is_negotiable' in request.data:
            is_negotiable_str = str(request.data.get('is_negotiable')).lower()
            item.is_negotiable = True if is_negotiable_str == 'true' else False

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

        gallery_urls = [img.image.url for img in item.gallery_images.all() if img.image]

        data = {
            'id': item.id,
            'title': item.title,
            'description': item.description,
            'price_per_day': item.price_per_day,
            'price_period': getattr(item, 'price_period', 'Day'),
            'condition': item.condition,
            'owner_username': item.owner.username,
            'image': image_url,
            'gallery_images': gallery_urls,
            'category': getattr(item, 'category', 'Other'),
            'replacement_value': getattr(item, 'replacement_value', 0.00),
            'min_rental_duration': getattr(item, 'min_rental_duration', '1 day'),
            'available_days': getattr(item, 'available_days', 'S,M,T,W,Th,F,Sa'),
            'delivery_option': getattr(item, 'delivery_option', 'Pickup only'),
            'pickup_location': getattr(item, 'pickup_location', ''),
            'cancellation_policy': getattr(item, 'cancellation_policy', 'flexible'),
            'is_negotiable': getattr(item, 'is_negotiable', True),
            'location': getattr(item, 'location', ''),
            'area': getattr(item, 'area', '')
        }
        return JsonResponse(data)
    except GearItem.DoesNotExist:
        return JsonResponse({'error': 'Equipment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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


class SubmitRentalRequestAPIView(APIView):
    def post(self, request):
        gear_id = request.data.get('gear_id')
        renter_id = request.data.get('renter_id')

        if not gear_id or not renter_id:
            return Response({"error": "Missing data required to process request."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            gear = GearItem.objects.get(id=gear_id)
            renter = CustomUser.objects.get(id=renter_id)

            if gear.owner.id == renter.id:
                return Response({"error": "You cannot rent your own equipment!"}, status=status.HTTP_400_BAD_REQUEST)

            if RentalRequest.objects.filter(gear=gear, renter=renter, status='Pending').exists():
                return Response({"error": "You already have a pending request for this item."},
                                status=status.HTTP_400_BAD_REQUEST)

            rental_req = RentalRequest.objects.create(
                gear=gear,
                renter=renter,
                owner=gear.owner,
                status='Pending'
            )

            return Response({
                "message": "Rental Request Sent!",
                "request_id": rental_req.id
            }, status=status.HTTP_201_CREATED)

        except (GearItem.DoesNotExist, CustomUser.DoesNotExist):
            return Response({"error": "Item or user not found."}, status=status.HTTP_404_NOT_FOUND)


def rental_chat_page(request, request_id):
    rental_request = get_object_or_404(RentalRequest, id=request_id)
    return render(request, 'rental_chat_placeholder.html', {'rental_request': rental_request})


class ChatHistoryAPIView(APIView):
    def get(self, request, request_id):
        messages = ChatMessage.objects.filter(rental_request_id=request_id).order_by('created_at')

        viewer_id = request.query_params.get('user_id')
        if viewer_id:
            ChatMessage.objects.filter(
                rental_request_id=request_id,
                is_read=False
            ).exclude(sender_id=viewer_id).update(is_read=True)

        data = []
        for msg in messages:
            data.append({
                'id': msg.id,
                'text': msg.text,
                'sender_id': msg.sender.id,
                'is_system_update': msg.is_system_update,
                'timestamp': localtime(msg.created_at).strftime("%I:%M %p")
            })

        return Response(data, status=status.HTTP_200_OK)


class UpdateChatPriceAPIView(APIView):
    def post(self, request, request_id):
        rental_req = get_object_or_404(RentalRequest, id=request_id)
        new_price_str = request.data.get('new_price')
        user_id = request.data.get('user_id')

        if not new_price_str or not user_id:
            return Response({"error": "Missing data format"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_price = Decimal(str(new_price_str))
        except InvalidOperation:
            return Response({"error": "Invalid price format."}, status=status.HTTP_400_BAD_REQUEST)

        if str(rental_req.owner.id) != str(user_id):
            return Response({"error": "Unauthorized. Only the owner can update the price."}, status=status.HTTP_403_FORBIDDEN)

        gear = rental_req.gear
        original_price = gear.price_per_day

        if new_price >= original_price:
            return Response({
                "error": f"You can only offer a discount. The original price is ৳{original_price:.2f}."
            }, status=status.HTTP_400_BAD_REQUEST)

        min_allowed_price = original_price * Decimal('0.60')
        if new_price < min_allowed_price:
            return Response({
                "error": f"You cannot deduct more than 40%. The minimum allowed price is ৳{min_allowed_price:.2f}."
            }, status=status.HTTP_400_BAD_REQUEST)

        rental_req.negotiated_price = new_price
        rental_req.save()

        system_text = f"System Update: The owner has offered a discounted rate of ৳{new_price:.2f} / {gear.price_period}."
        msg = ChatMessage.objects.create(
            rental_request=rental_req,
            sender=rental_req.owner,
            text=system_text,
            is_system_update=True
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{request_id}',
            {
                'type': 'chat_message',
                'message': system_text,
                'sender_id': rental_req.owner.id,
                'is_system_update': True,
                'new_price': str(new_price),
                'timestamp': localtime(msg.created_at).strftime("%I:%M %p")
            }
        )

        return Response({"message": "Discount offered successfully!"}, status=status.HTTP_200_OK)


class UserChatListAPIView(APIView):
    def get(self, request, user_id):
        user = get_object_or_404(CustomUser, id=user_id)

        requests = RentalRequest.objects.filter(Q(owner=user) | Q(renter=user))

        chat_list = []
        for req in requests:
            latest_msg = req.messages.order_by('-created_at').first()

            if req.owner == user:
                other_user = req.renter
                role_context = "Renter"
            else:
                other_user = req.owner
                role_context = "Owner"

            try:
                pfp = other_user.profile_picture.url if other_user.profile_picture else None
            except ValueError:
                pfp = None

            snippet = latest_msg.text if latest_msg else "No messages yet"
            if len(snippet) > 35:
                snippet = snippet[:32] + "..."

            has_unread = ChatMessage.objects.filter(
                rental_request=req,
                is_read=False
            ).exclude(sender=user).exists()

            chat_list.append({
                'request_id': req.id,
                'gear_title': req.gear.title,
                'other_user_name': other_user.username,
                'other_user_pfp': pfp,
                'role_context': role_context,
                'latest_message': snippet,
                'is_system': latest_msg.is_system_update if latest_msg else False,
                'has_unread': has_unread,
                'timestamp': localtime(latest_msg.created_at).strftime("%I:%M %p") if latest_msg else localtime(req.created_at).strftime("%I:%M %p"),
                'sort_time': latest_msg.created_at if latest_msg else req.created_at
            })

        chat_list.sort(key=lambda x: x['sort_time'], reverse=True)

        for item in chat_list:
            del item['sort_time']

        return Response(chat_list, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────
# HELPER: Brevo Email Sender
# ─────────────────────────────────────────────────────
def send_otp_email(email, code, purpose):
    if purpose == 'login':
        subject = '🔐 GearShare — Your Login OTP'
        body = f"Hello,\n\nYour login OTP is:\n\n{code}\n\nThis code expires in 10 minutes. Do NOT share it with anyone."
    else:
        subject = '🚨 GearShare — Password Reset'
        body = f"Hello,\n\nYour password reset code is:\n\n{code}\n\nIf you did not request this, ignore this email."

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)


# ─────────────────────────────────────────────────────
# SECURE 2FA & PASSWORD RESET APIs
# ─────────────────────────────────────────────────────
class SendLoginOTPView(APIView):
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
            if user.trust_tier == 'Suspended' and user.suspension_date:
                if timezone.now() > user.suspension_date + timedelta(days=3):
                    return Response({"error": "Account Permanently Locked"}, status=status.HTTP_403_FORBIDDEN)

            if user.auth_provider == 'google':
                return Response({"error": "Use 'Sign in with Google' for this account."},
                                status=status.HTTP_400_BAD_REQUEST)

            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expiration = timezone.now() + timedelta(minutes=10)
            user.otp_failed_attempts = 0
            user.save()

            send_otp_email(user.email, otp, 'login')

            return Response({"message": "OTP sent!", "email": user.email}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class VerifyLoginOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            user = CustomUser.objects.get(email=email)

            if user.otp_failed_attempts >= 3:
                user.otp_code = None
                user.save()
                return Response({"error": "Too many failed attempts. Request a new OTP."},
                                status=status.HTTP_403_FORBIDDEN)

            if not user.otp_expiration or timezone.now() > user.otp_expiration:
                return Response({"error": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)

            if user.otp_code != otp:
                user.otp_failed_attempts += 1
                user.save()
                return Response({"error": f"Invalid OTP. {3 - user.otp_failed_attempts} attempts left."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Success!
            user.otp_code = None
            user.otp_expiration = None
            user.otp_failed_attempts = 0
            user.save()

            try:
                profile_pic_url = user.profile_picture.url if user.profile_picture else None
            except ValueError:
                profile_pic_url = None

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

        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class SendResetOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            if user.auth_provider == 'google':
                return Response({"message": "If this email exists, an OTP has been sent."},
                                status=status.HTTP_200_OK)

            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expiration = timezone.now() + timedelta(minutes=10)
            user.otp_failed_attempts = 0
            user.save()

            send_otp_email(user.email, otp, 'reset')
        except CustomUser.DoesNotExist:
            pass
        return Response({"message": "If this email exists, an OTP has been sent."}, status=status.HTTP_200_OK)


class ResetPasswordWithOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        try:
            user = CustomUser.objects.get(email=email)

            if user.otp_failed_attempts >= 3:
                user.otp_code = None
                user.save()
                return Response({"error": "Too many failed attempts. Request a new OTP."},
                                status=status.HTTP_403_FORBIDDEN)

            if not user.otp_expiration or timezone.now() > user.otp_expiration:
                return Response({"error": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)

            if user.otp_code != otp:
                user.otp_failed_attempts += 1
                user.save()
                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.otp_code = None
            user.otp_expiration = None
            user.otp_failed_attempts = 0
            user.save()

            return Response({"message": "Password reset successfully!"}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"error": "Invalid request."}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────
# GOOGLE OAUTH: REDIRECT & CALLBACK
# ─────────────────────────────────────────────────────
class GoogleLoginRedirectView(APIView):
    def get(self, request):
        google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account"
        }
        url = f"{google_auth_url}?{urlencode(params)}"
        return redirect(url)


class GoogleAuthCallbackView(APIView):
    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return HttpResponse("Error: No code provided by Google.", status=400)

        # 1. Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI
        }
        res = requests.post(token_url, data=data)
        if not res.ok:
            return HttpResponse("Error: Failed to exchange token with Google.", status=400)

        access_token = res.json().get("access_token")

        # 2. Fetch User Info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        user_res = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
        if not user_res.ok:
            return HttpResponse("Error: Failed to fetch user profile.", status=400)

        user_data = user_res.json()
        email = user_data.get("email")
        google_id = user_data.get("id")
        first_name = user_data.get("given_name", "")
        last_name = user_data.get("family_name", "")

        # 3. Look up existing account — Google OAuth is sign-in only, not registration
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return render(request, 'no_account.html', {'email': email})

        # Link Google ID to existing account on first Google sign-in
        if not user.google_id:
            user.google_id = google_id
            user.auth_provider = 'google'
            user.save()

        # 4. Generate Frontend Payload (Invisible Redirect)
        html = f"""
        <html>
        <body style="background: #111827; color: #F97316; font-family: sans-serif; text-align: center; padding-top: 5rem;">
            <h2>Google Link Established. Entering Vault...</h2>
            <script>
                localStorage.setItem('gearshare_user_id', '{user.id}');
                localStorage.setItem('gearshare_username', '{user.username}');
                localStorage.setItem('gearshare_role', '{user.role}');
                localStorage.setItem('gearshare_trust_tier', '{user.trust_tier}');
                localStorage.setItem('gearshare_trust_score', '{user.trust_score}');
                localStorage.setItem('gearshare_can_switch', '{str(user.can_switch_role).lower()}');
                window.location.href = '/dashboard/';
            </script>
        </body>
        </html>
        """
        return HttpResponse(html)