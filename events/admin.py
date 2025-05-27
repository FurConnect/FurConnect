from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Convention, ConventionDay, Panel, PanelHost, Tag, PanelHostOrder, PanelTag

class ConventionDayInline(admin.TabularInline):
    model = ConventionDay
    extra = 1

class PanelInline(admin.TabularInline):
    model = Panel
    extra = 1
    fields = ['title', 'description', 'start_time', 'end_time', 'room', 'cancelled']

class PanelHostOrderInline(admin.TabularInline):
    model = PanelHostOrder
    extra = 1
    ordering = ['priority']

class PanelTagInline(admin.TabularInline):
    model = PanelTag
    extra = 1
    ordering = ['priority']

@admin.register(Convention)
class ConventionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name',)
    inlines = [ConventionDayInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs.exists():
            convention = qs.first()
            # Set the site header to the convention's name
            admin.site.site_header = f"{convention.name} Admin"
            admin.site.site_title = f"{convention.name} Admin Portal"
            admin.site.index_title = f"Welcome to {convention.name} Admin Portal"
        return qs

    def changelist_view(self, request, extra_context=None):
        # If there's a convention, redirect to its edit page
        convention = Convention.objects.first()
        if convention:
            return redirect(reverse('admin:events_convention_change', args=[convention.pk]))
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        # Only allow adding if no convention exists
        return not Convention.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Never allow deletion of the convention
        return False

@admin.register(ConventionDay)
class ConventionDayAdmin(admin.ModelAdmin):
    list_display = ('convention', 'date')
    list_filter = ('convention', 'date')
    search_fields = ('convention__name',)
    inlines = [PanelInline]

@admin.register(Panel)
class PanelAdmin(admin.ModelAdmin):
    list_display = ('title', 'convention_day', 'start_time', 'end_time', 'room', 'is_featured', 'cancelled')
    list_filter = ('convention_day__convention', 'convention_day__date', 'is_featured', 'cancelled')
    search_fields = ('title', 'description', 'room__name')
    inlines = [PanelHostOrderInline, PanelTagInline]

@admin.register(PanelHost)
class PanelHostAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color')
    search_fields = ('name',)
