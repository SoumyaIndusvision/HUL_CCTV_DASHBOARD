from django.contrib import admin
from .models import Seracs, Section, Camera


@admin.register(Seracs)
class SeracsAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    ordering = ('id',)

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'serac')
    ordering = ('id',)


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('id' ,'name', 'ip_address', 'port', 'is_active', 'section')
    list_editable = ('is_active',)
    ordering = ('id',)
