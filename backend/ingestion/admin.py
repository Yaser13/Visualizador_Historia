from django.contrib import admin, messages

from .models import AgentRun, FetchedDocument, NewsSubmission
from .services import SubmissionError, publish_submission, reject_submission


class FetchedDocumentInline(admin.TabularInline):
    model = FetchedDocument
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('role', 'title', 'publisher', 'source', 'published_at', 'http_status', 'fetched_at', 'fetch_error')
    readonly_fields = fields


class AgentRunInline(admin.TabularInline):
    model = AgentRun
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('agent', 'status', 'model', 'prompt_version', 'tokens_in', 'tokens_out', 'started_at', 'finished_at', 'error')
    readonly_fields = fields


@admin.register(NewsSubmission)
class NewsSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'normalized_url', 'user', 'status', 'event', 'story', 'attempts', 'created_at', 'reviewed_by')
    list_filter = ('status', 'created_at')
    list_select_related = ('user', 'event', 'story', 'reviewed_by')
    search_fields = ('url', 'normalized_url', 'user__username', 'event__title', 'note')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user', 'event', 'story', 'target_story', 'reviewed_by')
    readonly_fields = ('normalized_url', 'attempts', 'created_at', 'updated_at', 'started_at', 'finished_at', 'reviewed_by')
    inlines = (FetchedDocumentInline, AgentRunInline)
    actions = ('publish_selected', 'reject_selected')
    fieldsets = (
        (None, {'fields': ('user', 'url', 'normalized_url', 'note', 'target_story')}),
        ('Proceso', {'fields': ('status', 'step_detail', 'error', 'attempts', 'created_at', 'updated_at', 'started_at', 'finished_at')}),
        ('Resultado y revisión', {'fields': ('event', 'story', 'reviewed_by', 'review_note'),
                                  'description': 'Para rechazar desde la lista, escribe primero el motivo en «Review note».'}),
    )

    def _apply(self, request, queryset, action, verb):
        done = 0
        for submission in queryset:
            try:
                action(submission)
            except SubmissionError as error:
                self.message_user(request, f'#{submission.pk}: {error.message}', messages.ERROR)
            else:
                done += 1
        if done:
            self.message_user(request, f'{done} envío(s) {verb}.', messages.SUCCESS)

    @admin.action(description='Publicar los envíos seleccionados (solo en revisión)')
    def publish_selected(self, request, queryset):
        self._apply(request, queryset, lambda item: publish_submission(item, request.user, item.review_note), 'publicados')

    @admin.action(description='Rechazar los envíos seleccionados (usa «Review note» como motivo)')
    def reject_selected(self, request, queryset):
        self._apply(request, queryset, lambda item: reject_submission(item, request.user, item.review_note), 'rechazados')


@admin.register(FetchedDocument)
class FetchedDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'submission', 'role', 'title', 'publisher', 'published_at', 'http_status', 'fetched_at')
    list_filter = ('role',)
    list_select_related = ('submission',)
    search_fields = ('title', 'publisher', 'source__url')
    raw_id_fields = ('submission', 'source')


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'submission', 'agent', 'status', 'model', 'prompt_version', 'started_at', 'finished_at')
    list_filter = ('agent', 'status')
    list_select_related = ('submission',)
    raw_id_fields = ('submission',)
