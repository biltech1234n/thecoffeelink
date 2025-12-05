from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .models import User
from .forms import BuyerRegisterForm, SellerRegisterForm, AdminRegisterForm, RoleBasedLoginForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import UserUpdateForm
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy

# --- HELPER FOR LOGIN ---
def role_login(request, role, template_name, success_url):
    if request.method == 'POST':
        form = RoleBasedLoginForm(request, data=request.POST, role=role)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(success_url)
    else:
        form = RoleBasedLoginForm(role=role)
    return render(request, template_name, {'form': form, 'role': role})

# --- ADMIN VIEWS ---
def admin_register(request):
    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('admin_dashboard')
    else:
        form = AdminRegisterForm()
    return render(request, 'accounts/admin/register.html', {'form': form})

def admin_login(request):
    return role_login(request, User.ADMIN, 'accounts/admin/login.html', 'admin_dashboard')

# --- SELLER VIEWS ---
def seller_register(request):
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created. Verification pending.")
            return redirect('seller_dashboard')
    else:
        form = SellerRegisterForm()
    return render(request, 'accounts/seller/register.html', {'form': form})

def seller_login(request):
    return role_login(request, User.SELLER, 'accounts/seller/login.html', 'seller_dashboard')

# --- BUYER VIEWS ---
def buyer_register(request):
    if request.method == 'POST':
        form = BuyerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = BuyerRegisterForm()
    return render(request, 'accounts/buyer/register.html', {'form': form})

def buyer_login(request):
    return role_login(request, User.BUYER, 'accounts/buyer/login.html', 'home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)

    context = {
        'form': form,
        'orders_count': request.user.order_set.count() if hasattr(request.user, 'order_set') else 0,
        'date_joined': request.user.date_joined
    }
    return render(request, 'accounts/profile.html', context)

class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_message = "Your password has been changed successfully."
    success_url = reverse_lazy('profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass user role/data if needed for the sidebar
        return context
