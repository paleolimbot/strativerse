
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.html import format_html, mark_safe
from django.contrib.contenttypes.admin import GenericTabularInline
from reversion.admin import VersionAdmin
import reversion

from . import models


# ---- inlines ----

class TagInline(GenericTabularInline):
    model = models.Tag
    extra = 1


class AttachmentInline(GenericTabularInline):
    model = models.Attachment
    extra = 1


class ContactInfoInline(admin.TabularInline):
    model = models.ContactInfo
    extra = 1


class AliasInline(admin.TabularInline):
    model = models.Alias
    extra = 1


class AuthorshipInline(admin.TabularInline):
    model = models.Authorship
    autocomplete_fields = ['person']


class RecordFeatureInline(admin.TabularInline):
    model = models.RecordFeatureRelation
    extra = 1
    autocomplete_fields = ['feature']


class RecordAuthorshipInline(admin.TabularInline):
    model = models.RecordAuthorship
    extra = 1
    autocomplete_fields = ['person']


class RecordReferenceInline(admin.TabularInline):
    model = models.RecordReference
    extra = 1
    autocomplete_fields = ['publication']


# ---- admins ----

@admin.register(models.Feature)
class FeatureAdmin(VersionAdmin):
    inlines = [TagInline]
    list_display = ['name', 'type']
    search_fields = ['name', 'type']


@admin.register(models.Person)
class PersonAdmin(VersionAdmin):
    inlines = [ContactInfoInline, AliasInline, TagInline, AttachmentInline]
    list_display = ['last_name', 'given_names', 'suffix', 'publications']
    search_fields = ['last_name', 'given_names', 'aliases__alias']
    actions = ['combine_people']

    def publications(self, person, max_pubs=1):
        pubs = models.Publication.objects.filter(authorships__person=person).distinct()
        n_pubs = pubs.count()
        out = ', '.join(str(pub.admin_link(text=str(pub))) for pub in pubs[:max_pubs])
        if n_pubs > max_pubs:

            more = format_html(
                ' <a href="{}?authorships__person__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_publication_changelist'),
                person.id,
                n_pubs - max_pubs
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)

    def combine_people(self, request, queryset):
        people = list(queryset)
        if len(people) < 2:
            self.message_user(request, 'Two or more people must be selected.')
            return

        with reversion.create_revision(atomic=True):
            all_people = ', '.join(str(p) for p in people)
            target_person = models.Person.combine_people(people)

            self.message_user(request, 'Updated %s person objects; Combined %s' % (len(people), all_people))
            reversion.set_user(request.user)
            reversion.set_comment('Combined ' + all_people)
            return HttpResponseRedirect(
                reverse_lazy('admin:strativerse_person_change', kwargs={'object_id': target_person.pk})
            )
    combine_people.short_description = 'Combine person objects'


class FilterableRelatedOnlyFilter(admin.RelatedOnlyFieldListFilter):
    template = 'strativerse/admin/filterable_filter.html'


@admin.register(models.Publication)
class PublicationAdmin(VersionAdmin):
    inlines = [AuthorshipInline, TagInline, AttachmentInline]
    list_display = ['author_date_key', 'title', 'year', 'external_link', 'slug']
    search_fields = ['authorships__person__last_name', 'authorships__person__given_names',
                     'authorships__person__aliases__alias', 'title', 'year', 'doi']
    list_filter = [
        ('authorships__person', FilterableRelatedOnlyFilter),
    ]


@admin.register(models.Record)
class RecordAdmin(VersionAdmin):
    inlines = [RecordFeatureInline, RecordAuthorshipInline, RecordReferenceInline, TagInline, AttachmentInline]
    list_display = ['author_date_key', 'name', 'date', 'type', 'description', 'geo_wkt']
    search_fields = ['name', 'date', 'description', ]
