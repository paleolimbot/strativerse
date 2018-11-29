
import datetime

from django.contrib import admin
from django.db.models import TextField
from django.forms import Textarea
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.html import format_html, mark_safe
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.translation import gettext_lazy as _

from reversion.admin import VersionAdmin
import reversion

from . import models


# ---- helper classes ----

# This text override gets used to keep the size down on TextField()s
small_text_overrides = {
    TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 40})},
}


class HiddenRelatedListFilter(admin.RelatedOnlyFieldListFilter):
    model = None

    def has_output(self):
        return len(self.used_parameters) > 0

    def choices(self, changelist):
        try:
            title = str(self.model.objects.get(id=self.used_parameters[self.lookup_kwarg]))
        except self.model.DoesNotExist:
            title = '<Unknown %s>' % self.title

        return [
            {
                'selected': False,
                'query_string': changelist.get_query_string(remove=self.expected_parameters()),
                'display': _('All')
            },
            {
                'selected': True,
                'query_string': changelist.get_query_string(self.used_parameters),
                'display': title,
            }
        ]

    def queryset(self, request, queryset):
        return queryset.filter(**self.used_parameters)


class AuthorListFilter(HiddenRelatedListFilter):
    title = 'Author'
    model = models.Person


class PublicationListFilter(HiddenRelatedListFilter):
    title = 'Publication'
    model = models.Publication


class RecordListFilter(HiddenRelatedListFilter):
    title = 'Record'
    model = models.Record


class ParameterListFilter(HiddenRelatedListFilter):
    title = 'Parameter'
    model = models.Parameter


# ---- inlines ----

class TagInline(GenericTabularInline):
    model = models.Tag
    extra = 1
    formfield_overrides = small_text_overrides


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


class RecordAuthorshipInline(admin.TabularInline):
    model = models.RecordAuthorship
    extra = 1
    autocomplete_fields = ['person']


class RecordReferenceInline(admin.TabularInline):
    model = models.RecordReference
    extra = 1
    autocomplete_fields = ['publication']


class RecordParameterInline(admin.TabularInline):
    model = models.RecordParameter
    autocomplete_fields = ['parameter']
    extra = 3


# ---- admins ----

@admin.register(models.Feature)
class FeatureAdmin(VersionAdmin):
    inlines = [TagInline, AttachmentInline]
    list_display = ['name', 'type']
    search_fields = ['name', 'type']
    list_filter = ['type']
    fields = ['name', 'type', 'parent', 'geo_wkt', 'geo_error', 'geo_elev', 'geo_elev_error', 'description']


@admin.register(models.Parameter)
class ParameterAdmin(VersionAdmin):
    list_display = ['name', 'slug', 'preparation', 'instrumentation', 'records']
    search_fields = ['name', 'slug', 'preparation', 'instrumentation']

    def records(self, param, max_pubs=1):
        pubs = models.Record.objects.filter(record_parameters__parameter=param).distinct()
        n_pubs = pubs.count()
        out = ', '.join(str(pub.admin_link(text=str(pub))) for pub in pubs[:max_pubs])
        if n_pubs > max_pubs:

            more = format_html(
                ' <a href="{}?record_parameters__parameter__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_record_changelist'),
                param.id,
                n_pubs - max_pubs
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)


@admin.register(models.Person)
class PersonAdmin(VersionAdmin):
    inlines = [ContactInfoInline, AliasInline, TagInline, AttachmentInline]
    list_display = ['last_name', 'given_names', 'suffix', 'external_link', 'publications', 'records']
    search_fields = ['last_name', 'given_names', 'aliases__alias']
    actions = ['combine_people']
    list_filter = [
        ('authorships__publication', PublicationListFilter),
        ('record_authorships__record', RecordListFilter),
    ]

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

    def records(self, person, max_pubs=1):
        pubs = models.Record.objects.filter(record_authorships__person=person).distinct()
        n_pubs = pubs.count()
        out = ', '.join(str(pub.admin_link(text=str(pub))) for pub in pubs[:max_pubs])
        if n_pubs > max_pubs:

            more = format_html(
                ' <a href="{}?record_authorships__person__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_record_changelist'),
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


@admin.register(models.Publication)
class PublicationAdmin(VersionAdmin):
    inlines = [AuthorshipInline, TagInline, AttachmentInline]
    list_display = ['author_date_key', 'title', 'year', 'external_link', 'authors', 'records']
    search_fields = ['authorships__person__last_name', 'authorships__person__given_names',
                     'authorships__person__aliases__alias', 'title', 'year', 'DOI']
    list_filter = [
        ('authorships__person', AuthorListFilter),
        ('record_uses__record', RecordListFilter),
        'year'
    ]
    actions = ['create_record']

    def authors(self, pub, max_auth=1):
        authors = pub.authorships.filter(role='author').order_by('order')
        n_auth = authors.count()
        out = ', '.join(str(auth.person.admin_link(text=str(auth.person))) for auth in authors[:max_auth])
        if n_auth > max_auth:

            more = format_html(
                ' <a href="{}?authorships__publication__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_person_changelist'),
                pub.id,
                n_auth - max_auth
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)

    def records(self, pub, max_pubs=1):
        pubs = models.Record.objects.filter(record_uses__publication=pub).distinct()
        n_pubs = pubs.count()
        out = ', '.join(str(pub.admin_link(text=str(pub))) for pub in pubs[:max_pubs])
        if n_pubs > max_pubs:

            more = format_html(
                ' <a href="{}?record_uses__publication__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_record_changelist'),
                pub.id,
                n_pubs - max_pubs
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)

    def create_record(self, request, queryset):
        with reversion.create_revision(atomic=True):
            all_people = []
            pubs = list(queryset)
            record = models.Record(name='New record', medium='lake_sediment', type='core')

            record.date_collected = datetime.date(pubs[0].year, 1, 1)
            record.save()
            for pub in pubs:
                for authorship in pub.authorships.filter(role='author'):
                    if authorship.person not in all_people:
                        all_people.append(authorship.person)
                models.RecordReference.objects.create(record=record, publication=pub, type='contains_data_from')
            for person in all_people:
                models.RecordAuthorship.objects.create(record=record, person=person, role='published')

            reversion.set_user(request.user)
            reversion.set_comment('Created a new record with {} ({} total)'.format(pubs[0], len(pubs)))

            return HttpResponseRedirect(
                reverse_lazy('admin:strativerse_record_change', kwargs={'object_id': record.pk})
            )
    create_record.short_description = 'Create a new record with selected publications'


@admin.register(models.Record)
class RecordAdmin(VersionAdmin):
    inlines = [RecordAuthorshipInline, RecordReferenceInline, RecordParameterInline, TagInline, AttachmentInline]
    autocomplete_fields = ['feature']
    list_display = ['author_date_key', 'name', 'date_collected', 'type', 'description', 'people', 'publications']
    search_fields = ['name', 'description', 'record_authorship__author__last_name']
    list_filter = [
        ('record_authorships__person', AuthorListFilter),
        ('record_uses__publication', PublicationListFilter),
        ('record_parameters__parameter', ParameterListFilter),
        'type'
    ]
    actions = ['duplicate_record']
    formfield_overrides = small_text_overrides
    fields = ['name', 'date_collected', 'published', 'medium', 'type',
              'feature', 'description',
              'geo_wkt', 'geo_error', 'resolution',
              'min_year', 'max_year', 'position_units']

    def duplicate_record(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Please select exactly one record.')
            return

        with reversion.create_revision(atomic=True):
            obj = queryset.first()
            new_record = models.duplicate_object(obj, name=obj.name + ' (copy)')

            reversion.set_user(request.user)
            reversion.set_comment('Record duplicated from {}'.format(obj))

            return HttpResponseRedirect(
                reverse_lazy('admin:strativerse_record_change', kwargs={'object_id': new_record.pk})
            )
    duplicate_record.short_description = 'Duplicate one record'

    def people(self, pub, max_auth=1):
        authors = pub.record_authorships.all()
        n_auth = authors.count()
        out = ', '.join(str(auth.person.admin_link(text=str(auth.person))) for auth in authors[:max_auth])
        if n_auth > max_auth:

            more = format_html(
                ' <a href="{}?record_authorships__record__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_person_changelist'),
                pub.id,
                n_auth - max_auth
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)

    def publications(self, record, max_pubs=1):
        pubs = models.Publication.objects.filter(record_uses__record=record).distinct()
        n_pubs = pubs.count()
        out = ', '.join(str(pub.admin_link(text=str(pub))) for pub in pubs[:max_pubs])
        if n_pubs > max_pubs:

            more = format_html(
                ' <a href="{}?record_uses__record__id__exact={}">+{} more</a>',
                reverse_lazy('admin:strativerse_publication_changelist'),
                record.id,
                n_pubs - max_pubs
            )
            return mark_safe(out + more)
        else:
            return mark_safe(out)
