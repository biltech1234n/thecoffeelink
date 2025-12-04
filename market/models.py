from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField  # <--- Import this

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Green', 'Green Coffee Beans'),
        ('Roasted', 'Roasted Coffee'),
        ('Ground', 'Ground Coffee'),
        ('Equipment', 'Machinery'),
    ]

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Green')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # CHANGED: Use CloudinaryField instead of ImageField
    # 'folder' organizes images in your Cloudinary dashboard
    image = CloudinaryField('image', folder='products', blank=True, null=True)
    
    description = models.TextField()
    
    # Soft Delete & Active Status
    is_active = models.BooleanField(default=True) # Seller sets this false to "remove"
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Declined', 'Declined'),
        ('Paid', 'Paid'),
        ('Shipped', 'Shipped'),
    ]

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    quantity = models.IntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_price = self.product.price * self.quantity
        super().save(*args, **kwargs)
        

class SellerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_profile')
    is_farmer = models.BooleanField(default=False)
    is_roaster = models.BooleanField(default=False)
    is_exporter = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)
    company_name = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Profile: {self.user.username}"

# Hook to auto-create this profile when a Seller is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_seller_profile(sender, instance, created, **kwargs):
    # Only create profile if the user role is 'seller'
    if created and getattr(instance, 'role', '') == 'seller':
        SellerProfile.objects.create(user=instance)