from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import (
    SuperCategory,
    Category,
    SubCategory,
    SubSubCategory
)


admin.site.register(SuperCategory, ImportExportModelAdmin)
admin.site.register(Category, ImportExportModelAdmin)
admin.site.register(SubCategory, ImportExportModelAdmin)
admin.site.register(SubSubCategory, ImportExportModelAdmin)