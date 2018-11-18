
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from reversion.admin import VersionAdmin
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
    list_display = ['last_name', 'given_names', 'suffix']
    search_fields = ['last_name', 'given_names', 'aliases__alias']


@admin.register(models.Publication)
class PublicationAdmin(VersionAdmin):
    inlines = [AuthorshipInline, TagInline, AttachmentInline]
    list_display = ['author_date_key', 'title', 'year', 'doi', 'url', 'slug']
    search_fields = ['authorships__person__last_name', 'authorships__person__given_names',
                     'authorships__person__aliases__alias', 'title', 'year', 'doi']


@admin.register(models.Record)
class RecordAdmin(VersionAdmin):
    inlines = [RecordFeatureInline, RecordAuthorshipInline, RecordReferenceInline, TagInline, AttachmentInline]
    list_display = ['author_date_key', 'name', 'date', 'type', 'description', 'geo_wkt']
    search_fields = ['name', 'date', 'description', ]
