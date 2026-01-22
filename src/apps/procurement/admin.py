from django.contrib import admin
from .models import ComparativeQuote, ComparativeItem, ComparativeSupplier, ComparativePrice

@admin.register(ComparativeQuote)
class ComparativeQuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "item_cotizado", "proyecto", "estado", "creado_por", "creado_en")
    readonly_fields = ("number", "creado_por", "creado_en")

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # solo cuando es nuevo
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

admin.site.register(ComparativeItem)
admin.site.register(ComparativeSupplier)
admin.site.register(ComparativePrice)
