import json

from products.models import (
    SuperCategory,
    Category,
    SubCategory,
    SubSubCategory,
)


def import_categories(json_path):

    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    # IMPORTANT CHANGE
    sections = payload["items"]

    # =====================================================
    # FIND SECTIONS
    # =====================================================

    super_category_section = next(
        x for x in sections
        if x["type"] == "super-category"
    )

    category_section = next(
        x for x in sections
        if x["type"] == "category"
    )

    sub_category_section = next(
        x for x in sections
        if x["type"] == "sub-category"
    )

    sub_sub_category_section = next(
        x for x in sections
        if x["type"] == "sub-sub-category"
    )

    # =====================================================
    # SUPER CATEGORY
    # =====================================================

    print("Importing Super Categories...")

    for item in super_category_section["data"]:

        SuperCategory.objects.update_or_create(
            id=int(item["id"]),
            defaults={
                "name": item["name"]
            }
        )

    # =====================================================
    # CATEGORY
    # =====================================================

    print("Importing Categories...")

    for item in category_section["data"]:

        parent = SuperCategory.objects.get(
            id=int(item["parent_id"])
        )

        Category.objects.update_or_create(
            id=int(item["id"]),
            defaults={
                "name": item["name"],
                "super_category": parent
            }
        )

    # =====================================================
    # SUB CATEGORY
    # =====================================================

    print("Importing Sub Categories...")

    for item in sub_category_section["data"]:

        parent = Category.objects.get(
            id=int(item["parent_id"])
        )

        SubCategory.objects.update_or_create(
            id=int(item["id"]),
            defaults={
                "name": item["name"],
                "category": parent
            }
        )

    # =====================================================
    # SUB SUB CATEGORY
    # =====================================================

    print("Importing Sub Sub Categories...")

    for item in sub_sub_category_section["data"]:

        parent = SubCategory.objects.get(
            id=int(item["parent_id"])
        )

        extra = item.get("data", {})

        SubSubCategory.objects.update_or_create(
            id=int(item["id"]),
            defaults={
                "name": item["name"],
                "sub_category": parent,
                "min_products": extra.get(
                    "min_products", 1
                ),
                "max_products": extra.get(
                    "max_products", 9
                ),
            }
        )

    print("Import Completed Successfully")