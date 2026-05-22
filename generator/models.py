
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
from products.models import SubSubCategory

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100, blank=True, null=True)
    credits = models.IntegerField(default=10)

    def __str__(self):
        return self.user.email
    

class GenerationHistory(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generations"
    )

    # MULTIPLE CATEGORIES
    categories = models.ManyToManyField(
        SubSubCategory,
        related_name="generation_histories"
    )

    meesho_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    uploaded_image = models.ImageField(
        upload_to="uploaded_images/"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        db_table = "generation_history"

        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):

        return (
            f"{self.user.email} - "
            f"{self.created_at}"
        )

class ActiveSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField()
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.ip_address}"



class DailyLabelSummary(models.Model):

    date = models.DateField(
        unique=True,
        db_index=True
    )

    total_pdfs = models.IntegerField(
        default=0
    )

    total_labels = models.IntegerField(
        default=0
    )

    last_used = models.DateTimeField(
        auto_now=True,
        db_index=True
    )

    class Meta:

        ordering = ['-date']

        indexes = [

            models.Index(
                fields=['date']
            ),

            models.Index(
                fields=['-last_used']
            ),

        ]

    def __str__(self):

        return self.date.strftime(
            '%d-%m-%Y'
        )
    
class MonthlyLabelSummary(models.Model):

    month = models.DateField(
        unique=True,
        db_index=True
    )

    total_pdfs = models.IntegerField(
        default=0
    )

    total_labels = models.IntegerField(
        default=0
    )

    last_used = models.DateTimeField(
        auto_now=True,
        db_index=True
    )