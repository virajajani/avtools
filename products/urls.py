# products/urls.py

from django.urls import path
from .views import category_token, search_categories

urlpatterns = [
    path( "search-categories/", search_categories, name="search_categories"),
    path("category-token/", category_token, name="category_token"),
]