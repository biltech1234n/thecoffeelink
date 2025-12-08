from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q, Value, DecimalField, Count
from django.db.models.functions import Coalesce 
from django.contrib.auth import get_user_model
import json

# Import Models
from .models import Product, Order, BusinessProfile, BusinessCertification
from core.models import Notification 
from .forms import CertificationForm 
# pyment
from django.conf import settings
import stripe
import requests
# At the top of market/views.py, make sure you have these imports:
from django.urls import reverse
# Get the User model safely
User = get_user_model()

# ==========================
# 1. MARKETPLACE VIEWS
# ==========================

def product_list(request):
    products = Product.objects.filter(is_active=True, seller__is_verified=True)
    
    q = request.GET.get('q')
    category = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort')

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        products = products.filter(category=category)
    if min_price:
        try: products = products.filter(price__gte=float(min_price))
        except: pass
    if max_price:
        try: products = products.filter(price__lte=float(max_price))
        except: pass

    if sort_by == 'price_asc': products = products.order_by('price')
    elif sort_by == 'price_desc': products = products.order_by('-price')
    else: products = products.order_by('-created_at')

    categories = Product.CATEGORY_CHOICES 
    context = {'products': products, 'categories': categories}
    return render(request, 'market/list.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'market/detail.html', {'product': product})

# ==========================
# 2. SELLER DASHBOARD
# ==========================

@login_required
def seller_dashboard(request):
    if request.user.role != 'seller': return redirect('home')

    if not request.user.is_verified:
        messages.warning(request, "Verification required.")

    my_products = Product.objects.filter(seller=request.user, is_active=True)
    my_orders = Order.objects.filter(product__seller=request.user)
    
    valid_statuses = ['Paid', 'Shipped', 'Delivered']
    revenue = my_orders.filter(status__in=valid_statuses).aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    status_data = list(my_orders.values('status').annotate(count=Count('status')))
    labels = [x['status'] for x in status_data]
    values = [x['count'] for x in status_data]

    context = {
        'products_count': my_products.count(),
        'orders_count': my_orders.count(),
        'revenue': revenue,
        'chart_labels': json.dumps(labels),
        'chart_values': json.dumps(values)
    }
    return render(request, 'seller_panel/dashboard.html', context)

@login_required
def seller_products(request):
    if request.user.role != 'seller': return redirect('home')

    if request.method == 'POST':
        if not request.user.is_verified:
            messages.error(request, "Verification required.")
            return redirect('seller_products')

        action = request.POST.get('action')
        
        if action == 'add':
            Product.objects.create(
                seller=request.user,
                name=request.POST.get('name'),
                category=request.POST.get('category'),
                price=request.POST.get('price'),
                description=request.POST.get('description'),
                image=request.FILES.get('image')
            )
            messages.success(request, "Product listed.")
            
        elif action == 'remove':
            p_id = request.POST.get('product_id')
            p = get_object_or_404(Product, id=p_id, seller=request.user)
            p.is_active = False 
            p.save()
            messages.warning(request, "Product removed.")
        
        return redirect('seller_products')

    products = Product.objects.filter(seller=request.user, is_active=True)
    return render(request, 'seller_panel/products.html', {'products': products})

@login_required
def seller_orders(request):
    if request.user.role != 'seller': return redirect('home')

    if request.method == 'POST':
        o_id = request.POST.get('order_id')
        action = request.POST.get('action')
        order = get_object_or_404(Order, id=o_id, product__seller=request.user)
        
        if action == 'accept': order.status = 'Accepted'
        elif action == 'shipped': order.status = 'Shipped'
        elif action == 'delivered': order.status = 'Delivered'
        elif action == 'decline': order.status = 'Declined'
        elif action == 'pending': order.status = 'Pending'
        
        order.save()
        messages.success(request, f"Order updated: {order.status}")
        return redirect('seller_orders')

    orders = Order.objects.filter(product__seller=request.user).exclude(status='Pending').order_by('-created_at')
    return render(request, 'seller_panel/orders.html', {'orders': orders})

# ==========================
# 3. UNIFIED BUSINESS PROFILE
# ==========================
@login_required
def business_profile(request):
    profile, created = BusinessProfile.objects.get_or_create(user=request.user)
    cert_form = CertificationForm()

    # --- 1. HANDLE FORMS ---
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile.company_name = request.POST.get('company_name', '')
            profile.country = request.POST.get('country', '')
            profile.city = request.POST.get('city', '')
            profile.description = request.POST.get('description', '')
            profile.core_products = request.POST.get('core_products', '')
            
            # Roles
            profile.is_farmer = 'is_farmer' in request.POST
            profile.is_roaster = 'is_roaster' in request.POST
            profile.is_exporter = 'is_exporter' in request.POST
            profile.is_supplier = 'is_supplier' in request.POST

            if 'logo' in request.FILES:
                profile.logo = request.FILES['logo']
            
            profile.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('business_profile')

        elif 'upload_cert' in request.POST:
            cert_form = CertificationForm(request.POST, request.FILES)
            if cert_form.is_valid():
                cert = cert_form.save(commit=False)
                cert.profile = profile 
                cert.save()
                messages.success(request, "Document uploaded successfully.")
                return redirect('business_profile')
            else:
                messages.error(request, "Error uploading document.")

    # --- 2. ANALYTICS & REVENUE ---
    now = timezone.now()
    valid_status = ['Paid', 'Shipped', 'Delivered']
    
    # Defaults
    val_today = 0
    val_month = 0
    val_year = 0
    label_1 = "Revenue Today" # Default to Seller terminology
    label_2 = "Active Listings"
    label_3 = "Total Sales"
    count_1 = 0 
    count_2 = 0
    
    # Ranking Defaults
    my_rank = "N/A"
    total_sellers = 0

    if request.user.role == 'seller':
        # SELLER LOGIC
        orders = Order.objects.filter(product__seller=request.user, status__in=valid_status)
        
        # Financials
        val_today = orders.filter(created_at__date=now.date()).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_month = orders.filter(created_at__month=now.month, created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_year = orders.filter(created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        count_1 = Product.objects.filter(seller=request.user, is_active=True).count()
        count_2 = orders.count()

        # --- MARKET RANKING ALGORITHM ---
        # 1. Annotate every seller with their total revenue
        sellers_ranked = User.objects.filter(role='seller').annotate(
            total_revenue=Coalesce(
                Sum('product__order__total_price', 
                    filter=Q(product__order__status__in=valid_status)
                ), 
                Value(0), 
                output_field=DecimalField()
            )
        ).order_by('-total_revenue')

        total_sellers = sellers_ranked.count()
        
        # 2. Find my index
        for rank, seller in enumerate(sellers_ranked, start=1):
            if seller.id == request.user.id:
                my_rank = rank
                break

    else:
        # BUYER LOGIC (Spend Analysis)
        label_1 = "Spend Today"
        label_2 = "Orders Placed"
        label_3 = "-" 
        
        orders = Order.objects.filter(buyer=request.user, status__in=valid_status)
        val_today = orders.filter(created_at__date=now.date()).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_month = orders.filter(created_at__month=now.month, created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_year = orders.filter(created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        count_1 = orders.count()

    # --- 3. CONTEXT ---
    context = {
        'profile': profile,
        'cert_form': cert_form,
        
        # Financial Values
        'val_today': val_today,
        'val_month': val_month,
        'val_year': val_year,
        
        # Dynamic Labels (So it works for Buyer & Seller)
        'label_1': label_1, 
        'label_2': label_2, 
        'label_3': label_3,
        
        # Stats
        'count_1': count_1,
        'count_2': count_2,
        
        # Ranking
        'my_rank': my_rank,
        'total_sellers': total_sellers,
        
        # Chart
        'chart_labels': json.dumps(['Today', 'This Month', 'This Year']),
        'chart_data': json.dumps([float(val_today), float(val_month), float(val_year)])
    }
    
    return render(request, 'market/business_profile.html', context)

@login_required
def view_business_profile(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    profile, created = BusinessProfile.objects.get_or_create(user=user_obj)

    # The SAME analytics logic you already have
    now = timezone.now()
    valid_status = ['Paid', 'Shipped', 'Delivered']

    # Financial defaults
    val_today = val_month = val_year = 0
    label_1 = "Revenue Today"
    label_2 = "Active Listings"
    label_3 = "Total Sales"
    count_1 = count_2 = 0
    my_rank = "N/A"
    total_sellers = 0

    # If seller → seller analytics
    if user_obj.role == 'seller':
        orders = Order.objects.filter(product__seller=user_obj, status__in=valid_status)

        val_today = orders.filter(created_at__date=now.date()).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_month = orders.filter(created_at__month=now.month, created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_year = orders.filter(created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0

        count_1 = Product.objects.filter(seller=user_obj, is_active=True).count()
        count_2 = orders.count()

        sellers_ranked = User.objects.filter(role='seller').annotate(
            total_revenue=Coalesce(
                Sum('product__order__total_price',
                    filter=Q(product__order__status__in=valid_status)
                ),
                Value(0),
                output_field=DecimalField()
            )
        ).order_by('-total_revenue')

        total_sellers = sellers_ranked.count()

        for rank, seller in enumerate(sellers_ranked, start=1):
            if seller.id == user_obj.id:
                my_rank = rank
                break

    # If buyer → buyer analytics
    else:
        label_1 = "Spend Today"
        label_2 = "Orders Placed"
        label_3 = "-"

        orders = Order.objects.filter(buyer=user_obj, status__in=valid_status)

        val_today = orders.filter(created_at__date=now.date()).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_month = orders.filter(created_at__month=now.month, created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0
        val_year = orders.filter(created_at__year=now.year).aggregate(Sum('total_price'))['total_price__sum'] or 0

        count_1 = orders.count()

    context = {
        'profile': profile,
        'view_user': user_obj,   # important!
        
        'val_today': val_today,
        'val_month': val_month,
        'val_year': val_year,

        'label_1': label_1,
        'label_2': label_2,
        'label_3': label_3,

        'count_1': count_1,
        'count_2': count_2,

        'my_rank': my_rank,
        'total_sellers': total_sellers,

        'chart_labels': json.dumps(['Today', 'This Month', 'This Year']),
        'chart_data': json.dumps([float(val_today), float(val_month), float(val_year)]),
    }

    return render(request, 'market/business_profile.html', context)

@login_required
def delete_certificate(request, cert_id):
    cert = get_object_or_404(BusinessCertification, id=cert_id, profile__user=request.user)
    cert.delete()
    messages.warning(request, "Document removed.")
    return redirect('business_profile')

def business_directory(request):
    """
    Directory to find Sellers.
    """
    profiles = BusinessProfile.objects.filter(user__role='seller')
    
    valid_statuses = ['Paid', 'Shipped', 'Delivered']
    profiles = profiles.annotate(
        successful_orders=Count(
            'user__product__order', 
            filter=Q(user__product__order__status__in=valid_statuses)
        )
    )

    query = request.GET.get('q')
    country = request.GET.get('country')
    verified = request.GET.get('verified_seller')

    if query:
        profiles = profiles.filter(
            Q(company_name__icontains=query) | 
            Q(core_products__icontains=query) |
            Q(user__username__icontains=query)
        )
    if country:
        profiles = profiles.filter(country=country)
    if verified == 'on':
        profiles = profiles.filter(user__is_verified=True)

    countries = BusinessProfile.objects.exclude(country='').values_list('country', flat=True).distinct()

    context = {'profiles': profiles, 'countries': countries}
    return render(request, 'market/business_directory.html', context)

def public_business_profile(request, seller_id):
    seller = get_object_or_404(User, id=seller_id)
    profile = get_object_or_404(BusinessProfile, user=seller)
    
    products = Product.objects.filter(seller=seller, is_active=True)
    certs = BusinessCertification.objects.filter(profile=profile, is_verified=True)
    
    valid_status = ['Paid', 'Shipped', 'Delivered']
    successful_orders = Order.objects.filter(product__seller=seller, status__in=valid_status).count()
    product_count_all = Product.objects.filter(seller=seller).count()

    
    context = {
        'seller': seller,
        'profile': profile,
        'products': products,
        'certs': certs,
        'successful_orders': successful_orders,
        'product_count_all': product_count_all,
    }
    return render(request, 'market/public_profile.html', context)



# ==========================
# 3. Order & Payment
# ==========================
@login_required
def create_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if not product.seller.is_verified:
        messages.error(request, "Seller not verified.")
        return redirect('product_list')

    if request.user == product.seller:
        messages.warning(request, "You cannot buy your own product.")
        return redirect('product_detail', product_id=product.id)

    if request.method == 'POST':
        qty = int(request.POST.get('quantity', 1))
        if qty < 1:
            messages.error(request, "Quantity must be at least 1.")
            return redirect('product_detail', product_id=product.id)

        # PROFESSIONAL FIX: Check if a Pending (Unpaid) order already exists
        existing_order = Order.objects.filter(
            buyer=request.user, 
            product=product, 
            status='Pending'
        ).first()

        if existing_order:
            # If exists, update the quantity and price, don't create a new one
            existing_order.quantity = qty
            existing_order.save() # This triggers the total_price calculation in models.py
            order = existing_order
            # Optional: Notify user they are resuming an order
            # messages.info(request, "Resuming your previous unpaid order.")
        else:
            # Only create a new order if no pending one exists
            order = Order.objects.create(
                buyer=request.user, 
                product=product,
                quantity=qty,
                total_price=product.price * qty,
                status='Pending'
            )
            
        return redirect('payment', order_id=order.id)
    
    return redirect('product_detail', product_id=product.id)

@login_required
def buyer_orders(request):
    orders = Order.objects.filter(buyer=request.user).select_related('product', 'product__seller').order_by('-created_at')
    total_spend = orders.filter(status__in=['Paid', 'Shipped', 'Delivered']).aggregate(Sum('total_price'))['total_price__sum'] or 0
    context = {
        'orders': orders,
        'total_spend': total_spend
    }
    return render(request, 'market/buyer_orders.html', context)

@login_required
def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if request.method == 'POST':
        if order.status == 'Paid':
            return redirect('buyer_orders')
            
        order.status = 'Paid'
        order.save()
        
        # --- ADD NOTIFICATIONS HERE TOO ---
        # 1. Notify Buyer
        Notification.objects.create(
            recipient=request.user,
            sender=order.product.seller,
            notification_type='order',
            message=f"Payment Successful: {order.product.name} ({order.quantity}kg)",
            link=reverse('buyer_orders')
        )
        
        # 2. Notify Seller
        Notification.objects.create(
            recipient=order.product.seller,
            sender=request.user,
            notification_type='order',
            message=f"New Sale! {request.user.username} bought {order.quantity}kg.",
            link=reverse('seller_orders')
        )
        # ----------------------------------

        messages.success(request, "Payment successful!")
        return redirect('buyer_orders')
        
    return render(request, 'market/payment.html', {'order': order})

stripe.api_key = settings.STRIPE_SECRET_KEY

def payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'market/payment.html', {'order': order})

def stripe_checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # FIX: Pass the order.id to the success_url
    success_url = request.build_absolute_uri(f'/payment-success/{order.id}/')
    
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': order.product.name},
                'unit_amount': int(order.product.price * 100),
            },
            'quantity': order.quantity,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=request.build_absolute_uri(f'/payment/{order.id}'), # Redirect back to payment page on cancel
    )
    return redirect(session.url)

def chapa_checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    # --- 1. FIXED EXCHANGE RATE ---
    USD_TO_ETB_RATE = 156.00
    
    # Calculate amount
    usd_amount = float(order.total_price)
    etb_amount = usd_amount * USD_TO_ETB_RATE
    
    chapa_endpoint = "https://api.chapa.co/v1/transaction/initialize"
    
    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    # FIX: Pass the order.id to the callback_url
    callback_url = request.build_absolute_uri(f'/payment-success/{order.id}/')

    data = {
        "amount": etb_amount,
        "currency": "ETB",
        "email": request.user.email,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "callback_url": callback_url,
        "return_url": callback_url, # Some APIs look for return_url
        "title": f"Payment for {order.product.name}"
    }
    
    response = requests.post(chapa_endpoint, json=data, headers=headers)
    result = response.json()
    
    if result.get('status') == 'success':
        return redirect(result['data']['checkout_url'])
    else:
        messages.error(request, "Payment gateway error.")
        return redirect('payment_page', order_id=order.id)

@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    if order.status == 'Paid':
        messages.info(request, "Order already processed.")
        return redirect('buyer_orders')

    order.status = 'Paid'
    order.save()

    Notification.objects.create(
        recipient=request.user,
        sender=order.product.seller,
        notification_type='order',
        message=f"Payment Successful: You ordered {order.quantity}kg of {order.product.name}.",
        link=reverse('buyer_orders')  # Clicking takes them to their order list
    )

    Notification.objects.create(
        recipient=order.product.seller,
        sender=request.user,
        notification_type='order',
        message=f"New Sale! {request.user.username} bought {order.quantity}kg of {order.product.name} (${order.total_price}).",
        link=reverse('seller_orders') # Clicking takes them to their seller dashboard
    )
    
    messages.success(request, "Payment confirmed! Order placed successfully.")
    return redirect('buyer_orders')

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user, status='Pending')
    order.delete()
    messages.info(request, "Order cancelled.")
    return redirect('product_list')
