from django.contrib.auth.models import AbstractUser
from django.db import models
from cloudinary.models import CloudinaryField  # <--- Import this

class User(AbstractUser):
    BUYER = 'buyer'
    SELLER = 'seller'
    ADMIN = 'admin'
    
    ROLE_CHOICES = [
        (BUYER, 'Buyer'),
        (SELLER, 'Seller'),
        (ADMIN, 'Admin'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=BUYER)
    is_verified = models.BooleanField(default=False)

    def is_seller(self):
        return self.role == self.SELLER

class VerificationDoc(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_doc')
    
    # Use CloudinaryField with resource_type='auto' to allow PDFs and Images
    business_license = CloudinaryField(
        'business_license', 
        resource_type='auto', 
        folder='legal_docs/licenses'
    )
    
    id_card = CloudinaryField(
        'id_card', 
        resource_type='auto', 
        folder='legal_docs/ids'
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Docs for {self.user.username}"