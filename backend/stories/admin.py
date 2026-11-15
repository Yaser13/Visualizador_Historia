from django.contrib import admin

from .models import Actor, Claim, Effect, Event, Evidence, Location, Participation, Source, TimelineEntry, TimelineStory

admin.site.register([Actor, Claim, Effect, Evidence, Location, Participation, Source])


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'category', 'status', 'origin', 'start_date', 'date_precision', 'as_of')
    list_filter = ('status', 'origin', 'category', 'date_precision')
    search_fields = ('slug', 'title')
    raw_id_fields = ('submitted_by',)
    ordering = ('-start_date',)


class TimelineEntryInline(admin.TabularInline):
    model = TimelineEntry
    extra = 0
    autocomplete_fields = ('event',)
    fields = ('order', 'event')
    ordering = ('order',)


@admin.register(TimelineStory)
class TimelineStoryAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'kind', 'origin', 'as_of', 'entries_count', 'updated_at')
    list_filter = ('kind', 'origin')
    raw_id_fields = ('created_by',)
    search_fields = ('slug', 'title')
    readonly_fields = ('updated_at',)
    inlines = (TimelineEntryInline,)

    @admin.display(description='Hitos')
    def entries_count(self, obj):
        return obj.entries.count()


@admin.register(TimelineEntry)
class TimelineEntryAdmin(admin.ModelAdmin):
    list_display = ('story', 'order', 'event')
    list_filter = ('story',)
    list_select_related = ('story', 'event')
    autocomplete_fields = ('event',)
    ordering = ('story', 'order')
