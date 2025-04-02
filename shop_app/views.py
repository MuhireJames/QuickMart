from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Product, Cart, CartItem,Transaction
from .serializers import (
    ProductSerializer,
    DetailedProductSerializer,
    CartItemSerializer,
    SimpleCartSerializer,
    CartSerializer,
    UserSerializer,
    RegistrationSerializer,
    UserEditSerializer
)
from decimal import Decimal
import uuid
from django.conf import settings
import requests
import paypalrestsdk
from django.conf import settings

BASE_URL=settings.REACT_BASE_URL 
  
paypalrestsdk.configure({
    "mode":settings.PAYPAL_MODE,
    "client_id":settings.PAYPAL_CLIENT_ID,
    "client_secret":settings.PAYPAL_CLIENT_SECRET
})

@api_view(["GET"])
def products(request):
    products = Product.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def product_detail(request, slug):
    try:
        product = Product.objects.get(slug=slug)
        serializer = DetailedProductSerializer(product)
        return Response(serializer.data)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
def add_item(request):
    try:
        cart_code = request.data.get("cart_code")
        product_id = request.data.get("product_id")

        cart, created = Cart.objects.get_or_create(cart_code=cart_code)
        product = Product.objects.get(id=product_id)

        cartitem, created = CartItem.objects.get_or_create(cart=cart, product=product)

        cartitem.quantity = 1
        cartitem.save()

        serializer = CartItemSerializer(cartitem)
        return Response({"data": serializer.data, "message": "CartItem created successfully"}, status=201)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["GET"])
def product_in_cart(request):
    try:
        cart_code = request.query_params.get("cart_code")
        product_id = request.query_params.get("product_id")

        cart = Cart.objects.get(cart_code=cart_code)
        product = Product.objects.get(id=product_id)

        product_exists_in_cart = CartItem.objects.filter(cart=cart, product=product).exists()
        return Response({"product_in_cart": product_exists_in_cart})
    except Cart.DoesNotExist:
        return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def get_cart_stats(request):
    try:
        cart_code = request.query_params.get("cart_code")
        cart = Cart.objects.get(cart_code=cart_code, paid=False)
        serializer = SimpleCartSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def get_cart(request):
    try:
        cart_code = request.query_params.get("cart_code")
        cart = Cart.objects.get(cart_code=cart_code, paid=False)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["PATCH"])
def update_quantity(request):
    try:
        cartitem_id = request.data.get("item_id")
        quantity = request.data.get("quantity")
        quantity = int(quantity)
        cartitem = CartItem.objects.get(id=cartitem_id)
        cartitem.quantity = quantity
        cartitem.save()

        serializer = CartItemSerializer(cartitem)

        return Response({"data": serializer.data, "message": "Cart item quantity updated successfully"})

    except CartItem.DoesNotExist:
        return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["POST"])
def delete_cartitem(request):
    try:
        cartitem_id = request.data.get("item_id")
        cartitem = CartItem.objects.get(id=cartitem_id)
        cartitem.delete()
        return Response({"message": "Cart item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
    except CartItem.DoesNotExist:
        return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_username(request):
    user = request.user
    return Response({"username": user.username})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_info(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def registerView(request):
    serializer = RegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            return Response({"message": "User created successfully!"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    if(request.user):
        try:
        
            tx_ref = str(uuid.uuid4())  # Generate a unique transaction reference
            cart_code = request.data.get("cart_code")
            cart = Cart.objects.get(cart_code=cart_code)  
            user = request.user  

            # Calculate the total amount
            amount = sum([item.quantity * item.product.price for item in cart.items.all()])
            
            # Ensure the amount is a Decimal type for consistency
            tax = Decimal("4.00")
            total_amount = amount + tax
            currency = "USD"
            
            # Define the redirect URL after payment
            redirect_url = f"{BASE_URL}/payment-status/"
            
            # Create the transaction record in the database
            transaction = Transaction.objects.create(
                ref=tx_ref,
                cart=cart,
                amount=total_amount,
                currency=currency,
                user=user,
                status="pending"
            )
            
            # Flutterwave API payload
            flutterwave_payload = {
                "tx_ref": tx_ref,
                "amount": str(total_amount), 
                "currency": currency,
                "redirect_url": redirect_url,
                "customer": {
                    "email": user.email,
                    "name": user.username,
                    "phonenumber": user.phone
                },
                "customizations": {
                    "title": "Shoppit Payment"
                }
            }
            
            # Set up headers for the Flutterwave API request
            headers = {
                "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            # Make the API request to Flutterwave
            response = requests.post(
                "https://api.flutterwave.com/v3/payments",
                json=flutterwave_payload,
                headers=headers
            )
            
            # Handle the response from Flutterwave
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(response.json(), status=response.status_code)  # Corrected status code access
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(["POST"])
def payment_callback(request):
    status=request.GET.get('status')
    tx_ref=request.GET.get('tx_ref')
    transaction_id=request.GET.get('transaction_id')

    user=request.user

    if status == 'successful':
        headers={
            "Authorization":f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"
        }

        response=requests.get(f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify",headers=headers)
        response_data=response.json()

        if response_data['status'] == "success":
            transaction=Transaction.objects.get(ref=tx_ref)

            # confirm the transaction details
            if (response_data['data']['status'] == "successful" and float(response_data['data']['amount']) == float(transaction.amount) and response_data['data']['currency'] == transaction.currency):
                transaction.status ="completed"
                transaction.save()

                cart=transaction.cart
                cart.paid=True
                cart.user=user
                cart.save()

                return Response({'message':'Payment successful!','subMessage':'You have successfully made payment of items you purchased'})
            else:
                # payment verifucation failed
                return Response({'message':'Payment verification failed','subMessage':'Your payment verification failed!Try again'})
        else:
            return Response({'message':"Failed to verify transation with Flutterwave.",'subMessage':'We could not verify your transaction'}) 
    else:
        return Response({'message':'payment was not successfull.'},status=400)  

paypalrestsdk.configure({
    'mode': settings.PAYPAL_MODE,  
    'client_id': settings.PAYPAL_CLIENT_ID,
    'client_secret': settings.PAYPAL_CLIENT_SECRET,
})

@api_view(["POST"])
def initiate_paypal_payment(request):
    if request.method == "POST" and request.user.is_authenticated:
        tx_ref = str(uuid.uuid4())  # Generate a unique transaction reference ID
        user = request.user
        cart_code = request.data.get("cart_code")
        
        try:
            # Retrieve the cart
            cart = Cart.objects.get(cart_code=cart_code)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=404)

        # Calculate the amount (total cart value)
        amount = sum(item.product.price * item.quantity for item in cart.items.all())
        tax = Decimal("4.00")  # Tax can be adjusted or calculated dynamically
        total_amount = amount + tax

        # Create PayPal payment
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": f"{BASE_URL}/payment-status?paymentStatus=success&ref={tx_ref}",  # Redirect URL after successful payment
                "cancel_url": f"{BASE_URL}/payment-status?paymentStatus=cancel"  # Redirect URL after canceled payment
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": "Cart items",
                        "sku": "cart",
                        "price": str(total_amount),
                        "currency": "USD",
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": str(total_amount),
                    "currency": "USD"
                },
                "description": "Payment for cart items."
            }]
        })

        # Create a transaction record in your database with status 'pending'
        transaction, created = Transaction.objects.get_or_create(
            ref=tx_ref,
            cart=cart,
            amount=total_amount,
            user=user,
            status="pending"
        )

        # Process PayPal payment creation
        if payment.create():
            # Extract PayPal approval URL to redirect the user
            approval_url = next((link.href for link in payment.links if link.rel == "approval_url"), None)
            if approval_url:
                return Response({"approval_url": approval_url})
            else:
                return Response({"error": "PayPal approval URL not found."}, status=500)
        else:
            return Response({"error": payment.error}, status=400)
    else:
        return Response({"error": "Authentication required."}, status=401)  
     
@api_view(["POST"])
def paypal_payment_callback(request):
    payment_id=request.query_params.get('paymentId')
    payer_id=request.query_params.get('PayerID')
    ref=request.query_params.get('ref')

    user=request.user

    transaction=Transaction.objects.get(ref=ref)

    if payment_id and payer_id:
        payment=paypalrestsdk.Payment.find(payment_id)

        transaction.status='completed'
        transaction.save()
        cart=transaction.cart
        cart.paid=True
        cart.user=user
        cart.save()

        return Response({'message':'Payment successful!','subMessage':'You have successfully made payment of items you purchased'})
    
    else:  
        return Response({'error':'Payment verification failed'},status=400)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_user_profile(request):
    user = request.user
    serializer = UserEditSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        user.save()
        return Response({"message": "Profile updated successfully!", "data": serializer.data})
    
    return Response(serializer.errors, status=400)
  

















