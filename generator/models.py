
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