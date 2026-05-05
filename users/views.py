from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
# THE FIX: Added RentalRequest to the imports
from .models import CustomUser, RoleSwitchRequest, GearItem, GearGallery, RentalRequest
from django.utils import timezone
from datetime import timedelta
from .serializers import GearItemSerializer
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch


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
            if user.trust_tier == 'Suspended' and user.suspension_date:
                if timezone.now() > user.suspension_date + timedelta(days=3):
                    return Response({"error": "Account Permanently Locked"}, status=status.HTTP_403_FORBIDDEN)

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

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


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
        user_clearance = 1.0
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                user_clearance = user.trust_score
            except CustomUser.DoesNotExist:
                pass

        items = GearItem.objects.filter(
            is_active=True,
            min_trust_tier__lte=user_clearance
        ).select_related('owner')

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
                owner=owner,
                title=request.data.get('title'),
                description=request.data.get('description'),
                price_per_day=request.data.get('price_per_day'),
                price_period=request.data.get('price_period', 'Day'),
                condition=request.data.get('condition', 'Good'),
                category=request.data.get('category', 'Other'),
                replacement_value=request.data.get('replacement_value') or 0.00,
                min_rental_duration=request.data.get('min_rental_duration', '1 day'),
                available_days=request.data.get('available_days', 'S,M,T,W,Th,F,Sa'),
                delivery_option=request.data.get('delivery_option', 'Pickup only'),
                pickup_location=request.data.get('pickup_location', ''),
                cancellation_policy=request.data.get('cancellation_policy', 'flexible')
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
        item.replacement_value = request.data.get('replacement_value', getattr(item, 'replacement_value', 0.00)) or 0.00
        item.min_rental_duration = request.data.get('min_rental_duration', getattr(item, 'min_rental_duration', '1 day'))
        item.available_days = request.data.get('available_days', getattr(item, 'available_days', 'S,M,T,W,Th,F,Sa'))
        item.delivery_option = request.data.get('delivery_option', getattr(item, 'delivery_option', 'Pickup only'))
        item.pickup_location = request.data.get('pickup_location', getattr(item, 'pickup_location', ''))
        item.cancellation_policy = request.data.get('cancellation_policy', getattr(item, 'cancellation_policy', 'flexible'))

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
            'cancellation_policy': getattr(item, 'cancellation_policy', 'flexible')
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


# --- NEW: RENTAL REQUEST & CHAT VIEWS ---

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

            # Prevent double-booking spam
            if RentalRequest.objects.filter(gear=gear, renter=renter, status='Pending').exists():
                return Response({"error": "You already have a pending request for this item."}, status=status.HTTP_400_BAD_REQUEST)

            # Create the actual rental record!
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
    # This serves the HTML template. We pass the request context so the page knows what item they are talking about.
    rental_request = get_object_or_404(RentalRequest, id=request_id)
    return render(request, 'rental_chat_placeholder.html', {'rental_request': rental_request})


# --- 1. HTML Page View ---
class ContractPageView(View):
    def get(self, request):
        context = {
            "owner_name": "Rahim Rahman",
            "renter_name": "Karim Khan",
            "gear_name": "Canon EOS R5 Camera",
            "gear_condition": "Excellent",
            "rental_duration": "10 May to 15 May 2026",
            "total_price": "7,500",
            "penalty_fee": "10,000 BDT",
        }
        return render(request, 'rental_contract.html', context)


# --- 2. PDF Download View ---
class GenerateContractPDFView(View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="GearShare_Rental_Contract.pdf"'

        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter

        owner_name = "Rahim Rahman (Owner)"
        renter_name = "Karim Khan (Renter)"
        gear_name = "Sony Alpha A7III Camera & Lens"
        rental_duration = "3 Days (May 10, 2026 to May 13, 2026)"
        penalty_fee = "5,000 BDT"

        p.setFont("Helvetica-Bold", 16)
        p.drawString(1 * inch, height - 1 * inch, "GearShare Rental Agreement")

        p.setFont("Helvetica-Bold", 12)
        p.drawString(1 * inch, height - 1.5 * inch, "1. Parties Involved:")
        p.setFont("Helvetica", 12)
        p.drawString(1.2 * inch, height - 1.8 * inch, f"Owner: {owner_name}")
        p.drawString(1.2 * inch, height - 2.1 * inch, f"Renter: {renter_name}")

        p.setFont("Helvetica-Bold", 12)
        p.drawString(1 * inch, height - 2.6 * inch, "2. Equipment Details & Duration:")
        p.setFont("Helvetica", 12)
        p.drawString(1.2 * inch, height - 2.9 * inch, f"Gear: {gear_name}")
        p.drawString(1.2 * inch, height - 3.2 * inch, f"Rental Period: {rental_duration}")

        p.setFont("Helvetica-Bold", 12)
        p.drawString(1 * inch, height - 3.7 * inch, "3. Terms & Penalty:")

        textobject = p.beginText(1 * inch, height - 4.1 * inch)
        textobject.setFont("Helvetica", 11)

        rules_lines = [
            "The Renter agrees to return the equipment in the exact condition it was received.",
            "If the Renter damages, loses, or fails to return the equipment within the agreed",
            f"time limits, a penalty of {penalty_fee} and/or the full replacement cost of the gear",
            "will be charged.",
            "",
            "Any breach of this agreement may result in permanent suspension from GearShare,",
            "and legal action may be taken against the Renter under the applicable laws."
        ]

        for line in rules_lines:
            textobject.textLine(line)

        p.drawText(textobject)

        p.drawString(1 * inch, 2 * inch, "_______________________")
        p.drawString(1 * inch, 1.8 * inch, "Signature of Owner")
        p.drawString(4.5 * inch, 2 * inch, "_______________________")
        p.drawString(4.5 * inch, 1.8 * inch, "Signature of Renter")

        p.showPage()
        p.save()
        return response