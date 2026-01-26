
# from django.db import models

# class ProductCategory(models.Model):
#     name = models.CharField(max_length=100)
#     base_weight = models.FloatField(help_text='Weight in grams')
    
#     def __str__(self):
#         return self.name

# class ShippingRate(models.Model):
#     ZONE_CHOICES = [
#         ('local', 'Local (Same City)'),
#         ('zonal', 'Zonal (Same State)'),
#         ('national', 'National (Other States)'),
#     ]
    
#     zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
#     min_weight = models.FloatField(help_text='Minimum weight in grams')
#     max_weight = models.FloatField(help_text='Maximum weight in grams')
#     rate = models.DecimalField(max_digits=6, decimal_places=2)
    
#     class Meta:
#         ordering = ['zone', 'min_weight']
    
#     def __str__(self):
#         return f"{self.zone} - {self.min_weight}g to {self.max_weight}g: ₹{self.rate}"

from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    credits = models.IntegerField(default=0)

    def __str__(self):
        return str(self.user)


class GenerationHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=100)
    net_weight = models.FloatField(default=0)

    meesho_price = models.FloatField(default=0)
    return_price = models.FloatField(default=0)
    mrp = models.FloatField(default=0)

    uploaded_image = models.ImageField(upload_to="uploaded_images/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.category} - {self.created_at}"

