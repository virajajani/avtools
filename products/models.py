from django.db import models


class SuperCategory(models.Model):
    id = models.BigIntegerField(primary_key=True)

    name = models.CharField(
        max_length=255,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "super_categories"

        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    id = models.BigIntegerField(primary_key=True)

    name = models.CharField(
        max_length=255,
        db_index=True
    )

    super_category = models.ForeignKey(
        SuperCategory,
        on_delete=models.CASCADE,
        related_name="categories",
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["super_category"]),
            models.Index(fields=["super_category", "name"]),
        ]

        unique_together = (
            "super_category",
            "name"
        )

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    id = models.BigIntegerField(primary_key=True)

    name = models.CharField(
        max_length=255,
        db_index=True
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="sub_categories",
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sub_categories"

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["category"]),
            models.Index(fields=["category", "name"]),
        ]

        unique_together = (
            "category",
            "name"
        )

    def __str__(self):
        return self.name


class SubSubCategory(models.Model):
    id = models.BigIntegerField(primary_key=True)

    name = models.CharField(
        max_length=255,
        db_index=True
    )

    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        related_name="sub_sub_categories",
        db_index=True
    )

    min_products = models.IntegerField(default=1)
    max_products = models.IntegerField(default=9)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sub_sub_categories"

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["sub_category"]),
            models.Index(fields=["sub_category", "name"]),
        ]

        unique_together = (
            "sub_category",
            "name"
        )

    def __str__(self):
        return self.name