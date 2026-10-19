from django.contrib import admin

from .models import AuditEvent, Equipment, Evaluation, Letter, Presentation, ProcessingWarning


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    list_display = ("correlative", "direction", "letter_date", "full_number", "created_by")
    search_fields = ("full_number",)
    list_filter = ("direction", "source")


admin.site.register(Equipment)
admin.site.register(Presentation)
admin.site.register(Evaluation)
admin.site.register(ProcessingWarning)
admin.site.register(AuditEvent)
