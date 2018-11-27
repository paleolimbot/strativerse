
import re
import json
import os
import copy
import unicodedata

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import RegexValidator, ValidationError
from django.db import models
from django.utils.html import format_html
from django.urls import reverse_lazy
from django.contrib.auth.models import User
import reversion

from .geometry import validate_wkt, wkt_bounds, wkt_geometry_type


class Tag(models.Model):
    type = models.CharField(max_length=55, default='tag')
    key = models.CharField(max_length=55, validators=[
        RegexValidator(r'^[A-Za-z0-9_]+$', message='Must only contain alphanumerics or the underscore')
    ])
    value = models.TextField()
    comment = models.TextField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id', 'type', 'key']
        ordering = ['type', 'key']

    def __str__(self):
        return '%s/%s=`%s`' % (self.type, self.key, self.value)


class Attachment(models.Model):
    type = models.CharField(max_length=55, default='attachment')
    key = models.CharField(max_length=55, validators=[
        RegexValidator(r'^[A-Za-z0-9_]+$', message='Must only contain alphanumerics or the underscore')
    ])
    comment = models.CharField(max_length=512)
    file = models.FileField(upload_to='attachments')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id', 'type', 'key']
        ordering = ['type', 'key']

    def __str__(self):
        return '%s/%s=`%s`' % (self.type, self.key, self.file.name)


class GeoModel(models.Model):
    geo_wkt = models.TextField(validators=[validate_wkt, ], blank=True)
    geo_error = models.FloatField(default=0)

    geo_elev = models.FloatField(default=0)
    geo_elev_error = models.FloatField(default=0)

    geo_xmin = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_xmax = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_ymin = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_ymax = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_type = models.CharField(max_length=55, blank=True, editable=False)

    class Meta:
        abstract = True

    def cache_bounds(self):
        bounds = wkt_bounds(self.geo_wkt)
        self.geo_type = wkt_geometry_type(self.geo_wkt)
        self.geo_xmin = bounds['xmin']
        self.geo_xmax = bounds['xmax']
        self.geo_ymin = bounds['ymin']
        self.geo_ymax = bounds['ymax']


class RecursiveModel(models.Model):
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    recursive_depth = models.IntegerField(default=0, editable=False)

    class Meta:
        abstract = True

    def _calculate_recursive_depth(self):
        if self.parent:
            return self.parent._calculate_recursive_depth() + 1
        else:
            return 0

    def cache_recursive_depth(self):
        self.recursive_depth = self._calculate_recursive_depth()


class LinkableModel(models.Model):

    class Meta:
        abstract = True

    def get_admin_url(self):
        return reverse_lazy('admin:strativerse_{}_change'.format(self._meta.model_name), kwargs={'object_id': self.pk})

    def get_absolute_url(self):
        return reverse_lazy('strativerse:detail', kwargs={'model': type(self).__name__.lower(), 'pk': self.pk})

    def get_external_url(self):
        return None

    def admin_link(self, text=None):
        if text is None:
            text = str(self)
        return format_html('<a href="{}">{}</a>', self.get_admin_url(), text)

    def link(self, text=None):
        if text is None:
            text = str(self)
        return format_html('<a href="{}">{}</a>', self.get_absolute_url(), text)

    def external_link(self, text=None, blank_text=''):
        url = self.get_external_url()
        if url is None and text is None:
            return blank_text
        elif url is None:
            return text() if callable(text) else text
        elif text is None:
            return format_html('<a href="{}" target="_blank">{}</a>', url, str(self))
        elif callable(text):
            return format_html('<a href="{}" target="_blank">{}</a>', url, text())
        else:
            return format_html('<a href="{}" target="_blank">{}</a>', url, text)


class TaggedModel(models.Model):
    tags = GenericRelation(Tag)

    class Meta:
        abstract = True


class AttachableModel(models.Model):
    attachments = GenericRelation(Attachment)

    class Meta:
        abstract = True


class Feature(TaggedModel, LinkableModel, AttachableModel, RecursiveModel, GeoModel):
    name = models.CharField(max_length=255)
    type = models.CharField(
        choices=[
            ('feature', 'Feature'),
            ('water_body', 'Water Body'),
            ('glacier', 'Glacier'),
            ('bog', 'Bog'),
            ('geopolitical_unit', 'Geopolitical Unit'),
            ('region', 'Region')
        ],
        default='feature',
        max_length=55
    )
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.cache_bounds()
        self.cache_recursive_depth()
        super().save(*args, **kwargs)

    def __str__(self):
        return '%s <%s %s>' % (self.name, self.type, self.pk)


class Person(TaggedModel, LinkableModel, AttachableModel):
    given_names = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)
    suffix = models.CharField(max_length=10, blank=True)
    orc_id = models.CharField(max_length=20, blank=True, validators=[
        RegexValidator(
            r'^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}$',
            message='Value must be a valid ORCID (0000-0000-0000-0000)'
        )
    ])

    class Meta:
        verbose_name_plural = 'people'
        ordering = ['last_name', 'given_names']

    def get_external_url(self):
        return 'https://orcid.org/' + self.orc_id if self.orc_id else None

    def external_link(self, text=None, blank_text=''):
        url = self.get_external_url()
        return blank_text if url is None else super().external_link(text=self.orc_id, blank_text=blank_text)

    def __str__(self):
        if self.given_names:
            return ' '.join((self.given_names, self.last_name))
        else:
            return self.last_name

    @staticmethod
    def combine_people(people):
        people = list(people)
        n_pubs = [p.authorships.all().count() for p in people]
        max_pubs = max(n_pubs)
        max_index = [i for i, n in enumerate(n_pubs) if n == max_pubs][0]

        target_person = people.pop(max_index)
        for renamed_person in people:
            # could use Queryset.update() here, but it doesn't send any signals to reversion
            # not important for Alias objects, since we're about to delete the objects
            # they come from and save the one they're going to
            Alias.objects.filter(person=renamed_person).update(person=target_person)
            for authorship in Authorship.objects.filter(person=renamed_person):
                authorship.person = target_person
                authorship.save()

            for authorship in RecordAuthorship.objects.filter(person=renamed_person):
                authorship.person = target_person
                authorship.save()

            for tag in list(renamed_person.tags.all()):
                try:
                    target_person.tags.get(type=tag.type, key=tag.key)
                except Tag.DoesNotExist:
                    tag.object_id = target_person.pk
                    tag.save()

            for attachment in list(renamed_person.attachments.all()):
                try:
                    target_person.attachments.get(type=attachment.type, key=attachment.key)
                except Tag.DoesNotExist:
                    attachment.object_id = target_person.pk
                    attachment.save()

            renamed_person.delete()

        target_person.save()
        return target_person


class ContactInfo(models.Model):
    updated = models.DateField()
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='contact')
    email = models.EmailField(max_length=255, blank=True)
    telephone = models.CharField(max_length=55, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'contact info'

    def __str__(self):
        info = []
        for key in ('email', 'telephone', 'address'):
            value = getattr(self, key)
            if value:
                info.append('%s: %s' % (key, value))
        if info:
            return ' // '.join(info)
        else:
            return '<no info>'


class Alias(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='aliases')
    alias = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = 'aliases'
        unique_together = ['person', 'alias']

    def __str__(self):
        return self.alias

    @staticmethod
    def clean_alias(value):
        return re.sub(r'([A-Z])\.', r'\1', value)


class Publication(TaggedModel, LinkableModel, AttachableModel):
    slug = models.CharField(max_length=55, unique=True)
    type = models.CharField(max_length=55, choices=[
        # source: https://github.com/citation-style-language/schema/blob/master/csl-types.rnc
        ('article', 'article'),
        ('article-journal', 'article-journal'),
        ('article-magazine', 'article-magazine'),
        ('article-newspaper', 'article-newspaper'),
        ('bill', 'bill'),
        ('book', 'book'),
        ('broadcast', 'broadcast'),
        ('chapter', 'chapter'),
        ('dataset', 'dataset'),
        ('entry', 'entry'),
        ('entry-dictionary', 'entry-dictionary'),
        ('entry-encyclopedia', 'entry-encyclopedia'),
        ('figure', 'figure'),
        ('graphic', 'graphic'),
        ('interview', 'interview'),
        ('legal_case', 'legal_case'),
        ('legislation', 'legislation'),
        ('manuscript', 'manuscript'),
        ('map', 'map'),
        ('motion_picture', 'motion_picture'),
        ('musical_score', 'musical_score'),
        ('pamphlet', 'pamphlet'),
        ('paper-conference', 'paper-conference'),
        ('patent', 'patent'),
        ('personal_communication', 'personal_communication'),
        ('post', 'post'),
        ('post-weblog', 'post-weblog'),
        ('report', 'report'),
        ('review', 'review'),
        ('review-book', 'review-book'),
        ('song', 'song'),
        ('speech', 'speech'),
        ('thesis', 'thesis'),
        ('treaty', 'treaty'),
        ('webpage', 'webpage'),
    ])
    title = models.CharField(max_length=1024)
    DOI = models.CharField(max_length=255, blank=True)
    URL = models.URLField(blank=True)
    abstract = models.TextField(blank=True)
    year = models.IntegerField()

    class Meta:
        ordering = ['slug']

    def get_external_url(self):
        if self.DOI:
            return 'https://doi.org/' + self.DOI
        elif self.URL:
            return self.URL
        else:
            return None

    def external_link(self, text=None, blank_text=''):
        if text is None:
            def text():
                if self.DOI:
                    return 'doi:' + self.DOI
                elif self.URL:
                    return self.URL
                else:
                    return blank_text

        return super().external_link(text, blank_text=blank_text)

    def update_from_csl_json(self, entry, update_authors=False, update_slug=False, update_tags=False):

        if not isinstance(entry, dict):
            raise ValidationError('entry must be a dictionary')

        entry = copy.deepcopy(entry)
        entry.pop('id', None)  # discard id given by file

        for key in ('title', 'abstract', 'DOI', 'URL', 'type'):
            if key in entry:
                setattr(self, key, entry.pop(key))

        # year is tricky to get, can be encoded in two ways
        # don't pop...this will get encoded in tags so detail is not lost
        try:
            if 'issued' in entry and 'date-parts' in entry['issued']:
                self.year = int(entry['issued']['date-parts'][0][0])
            elif 'issued' in entry and 'raw' in entry['issued']:
                self.year = int(entry['issued']['raw'][0].strip()[:4])
        except (ValueError, KeyError, TypeError):
            raise ValidationError('Could not extract year from entry')

        if update_authors:

            if not self.pk:
                self.save()
            else:
                # not sending a reversion signal, but we're about to update these anyway
                self.authorships.all().delete()

            for role in ('author', 'collection-editor', 'composer', 'container-author', 'director', 'editor',
                         'editorial-director', 'illustrator', 'interviewer', 'original-author',
                         'recipient', 'reviewed-author', 'translator'):
                # these shouldn't be popped, because they are used to generate the citation
                # this facilitates people's names being changed later and still being associated
                # with the publication, whose citation stays stable over time
                if role not in entry:
                    continue
                person_list = copy.deepcopy(entry[role])

                if not isinstance(person_list, list):
                    raise ValidationError('entry["{}"] is not a list'.format(role))

                for i, p in enumerate(person_list):
                    if not isinstance(p, dict):
                        raise ValidationError('entry["{}"][{}] is not a dict'.format(role, i))
                    last_name = p.pop('family', '')
                    first_name = p.pop('given', '')
                    suffix = p.pop('suffix', '')
                    if 'non-dropping-particle' in p:
                        last_name = p['non-dropping-particle'] + ' ' + last_name
                    if 'literal' in p:
                        last_name = p['literal']

                    if not last_name:
                        raise ValidationError('entry["%s"][%s] has no last name or literal element' % (role, i))
                    elif not first_name:
                        alias = last_name
                    else:
                        alias = '{}, {} {}'.format(last_name, first_name, suffix)
                    alias = Alias.clean_alias(alias)

                    try:
                        person = Alias.objects.get(alias=alias).person
                    except Alias.DoesNotExist:
                        person = Person.objects.create(
                            given_names=first_name,
                            last_name=last_name,
                            suffix=suffix
                        )
                        Alias.objects.create(person=person, alias=alias)

                    Authorship.objects.create(
                        publication=self,
                        person=person,
                        role=role,
                        order=i
                    )

        # generate a unique slug like 'dunnington_etal16'
        if update_slug:
            adk = self.author_date_key(parentheses=True)
            slug = re.sub(r'\([0-9]{2}([0-9]{2})\)', r'\1', adk).\
                replace(' and ', '_').\
                replace(' et al. ', '_etal').\
                replace('<no authors>', 'no_authors').\
                lower()

            # there shouldn't be any whitespace in the slug
            slug = re.sub(r'\s+', '', slug)

            # this gets rid of accents and weird but totally valid unicode characters
            slug = unicodedata.normalize('NFKD', slug).encode('ascii', 'ignore').decode('ascii')

            for suffix in ('', ) + tuple('abcdefghijklmnopqrstufwxyz'):
                try:
                    qs = Publication.objects.all()
                    if self.pk:
                        qs = qs.exclude(pk=self.pk)
                    qs.get(slug=slug + suffix)
                except Publication.DoesNotExist:
                    self.slug = slug + suffix
                    break
            else:
                raise ValidationError('Cannot create unique id for slug "{}"'.format(slug))

        # encode everything left in entry as tags
        if update_tags:
            if not self.pk:
                self.save()
            else:
                self.tags.filter(type='meta').delete()

            for key, value in entry.items():
                if isinstance(value, dict) or isinstance(value, list):
                    value = 'application/json:' + json.dumps(value)
                self.tags.create(type='meta', key=key, value=value)

    @staticmethod
    def import_csl_json(text, update_authors=True, user=None, chunk_size=25, quiet=True):

        text_label = re.sub(r'\s+', ' ', repr(text)[:100].replace('\n', ' '))
        if isinstance(text, str):
            if os.path.exists(text):
                with open(text, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
            else:
                entries = json.loads(text)
        else:
            entries = text

        if isinstance(entries, dict):
            entries = [entries]
        elif not isinstance(entries, list):
            raise ValidationError('text must be a list of CSL JSON entries')
        elif len(entries) == 0:
            return []

        items = []

        # chunk by for each revision to avoid too many variables error
        for chunk in range(int((len(entries) - 1) / chunk_size) + 1):
            if not quiet:
                print('Processing chunk {}'.format(chunk))

            with reversion.create_revision(atomic=True):
                chunk_entries = entries[(chunk * chunk_size):((chunk + 1) * chunk_size)]
                for entry in chunk_entries:
                    if not quiet:
                        print('Processing entry: {}'.format(entry.get('id', '<no id>')))

                    # check for key already in database by DOI (update everything except authorship if it is)
                    try:
                        if 'DOI' in entry:
                            pub = Publication.objects.get(DOI=entry['DOI'])
                        else:
                            pub = Publication()
                    except Publication.DoesNotExist:
                        pub = Publication()

                    pub.update_from_csl_json(entry, update_authors=update_authors, update_slug=True, update_tags=True)
                    pub.save()

                    # check for existing publication with same title and base slug
                    try:
                        slug_base = re.sub(r'[a-z]$', '', pub.slug)
                        existing_pub = Publication.objects.get(title=pub.title, slug__startswith=slug_base)
                        pub.delete()
                        existing_pub.update_from_csl_json(
                            entry, update_authors=update_authors, update_slug=True, update_tags=True
                        )
                        existing_pub.save()
                        pub = existing_pub
                    except Publication.DoesNotExist:
                        pass

                    items.append(pub)

                reversion.set_comment(
                    'CSL JSON import [chunk {}, {} items]: {}'.format(chunk+1, len(chunk_entries), text_label)
                )
                if user:
                    reversion.set_user(user)

        return items

    def author_date_key(self, parentheses=False):
        authorships = list(self.authorships.filter(role='author').order_by('order'))
        if len(authorships) == 0:
            author_text = '<no authors>'
        elif len(authorships) == 1:
            author_text = authorships[0].person.last_name
        elif len(authorships) == 2:
            author_text = '%s and %s' % (
                authorships[0].person.last_name,
                authorships[1].person.last_name
            )
        else:
            author_text = '%s et al.' % authorships[0].person.last_name

        if parentheses:
            return '%s (%s)' % (author_text, self.year)
        else:
            return '%s %s' % (author_text, self.year)

    def __str__(self):
        if len(self.title) > 25:
            title = self.title[:25].strip() + '...'
        else:
            title = self.title[:25]
        return '%s: "%s"' % (self.slug, title)


class Authorship(models.Model):
    publication = models.ForeignKey(Publication, models.CASCADE, related_name='authorships')
    person = models.ForeignKey(Person, models.PROTECT, related_name='authorships')
    role = models.CharField(max_length=55)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['role', 'order']

    def __str__(self):
        return '%s (%s)' % (self.person, self.role)


class Parameter(TaggedModel, AttachableModel, LinkableModel):
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, validators=[RegexValidator(r'^[^/][a-zA-Z_/]+[^/]$')], unique=True)
    description = models.TextField(blank=True)
    preparation = models.CharField(max_length=255)
    instrumentation = models.CharField(max_length=255)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Record(GeoModel, TaggedModel, AttachableModel, LinkableModel):
    name = models.CharField(max_length=255)
    date_collected = models.DateField()
    description = models.TextField(blank=True)
    feature = models.ForeignKey(Feature, on_delete=models.SET_NULL, blank=True, null=True)
    medium = models.CharField(
        choices=[
            ('lake_sediment', 'Lake Sediment'),
            ('marine_sediment', 'Marine Sediment'),
            ('glacier_ice', 'Glacier Ice'),
            ('peat', 'Peat'),
            ('lake_water', 'Lake Water'),
            ('river_water', 'River Water'),
            ('ocean_water', 'Ocean Water'),
            ('wood', 'Wood'),
            ('surficial_sediment', 'Surficial sediment'),
            ('rock', 'Rock'),
            ('mollusk_shell', 'Mollusk shell'),
            ('coral', 'Coral'),
            ('speleothem', 'Speleothem'),
            ('sclerosponge', 'Sclerosponge'),
            ('air', 'Air'),
            ('hybrid', 'Hybrid'),
            ('other', 'Other')
        ],
        max_length=55
    )
    type = models.CharField(
        choices=[
            ('samples', 'Samples'),
            ('core', 'Core'),
            ('section', 'Section'),
            ('sensor', 'Sensor'),
            ('other', 'Other')
        ],
        max_length=55
    )
    resolution = models.FloatField(blank=True, null=True, default=None)
    min_year = models.FloatField(blank=True, null=True, default=None)
    max_year = models.FloatField(blank=True, null=True, default=None)

    class Meta:
        ordering = ['date_collected']

    def save(self, *args, **kwargs):
        self.cache_bounds()
        super().save(*args, **kwargs)

    def author_date_key(self, parentheses=False):
        authorships = list(self.record_authorships.all().order_by('order'))
        if len(authorships) == 0:
            author_text = '<no authors>'
        elif len(authorships) == 1:
            author_text = authorships[0].person.last_name
        elif len(authorships) == 2:
            author_text = '%s and %s' % (
                authorships[0].person.last_name,
                authorships[1].person.last_name
            )
        else:
            author_text = '%s et al.' % authorships[0].person.last_name

        if parentheses:
            return '%s (%s)' % (author_text, self.date_collected.year)
        else:
            return '%s %s' % (author_text, self.date_collected.year)

    def __str__(self):
        return '%s: %s' % (self.author_date_key(), self.name)


class RecordAuthorship(models.Model):
    record = models.ForeignKey(Record, models.CASCADE, related_name='record_authorships')
    person = models.ForeignKey(Person, models.PROTECT, related_name='record_authorships')
    role = models.CharField(max_length=55, default='assisted', choices=[
        ('assisted', 'Assisted'),
        ('collected', 'Collected'),
        ('funded', 'Funded'),
        ('analyzed', 'Analyzed'),
        ('published', 'Published'),
        ('maintains', 'Maintains')
    ])
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return '%s (%s)' % (self.person, self.role)


class RecordReference(models.Model):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name='record_uses')
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='record_uses')
    type = models.CharField(max_length=55, default='refers_to', choices=[
        ('refers_to', 'Refers to'),
        ('contains_data_from', 'Contains data from')
    ])
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['publication__date']

    def __str__(self):
        return ' '.join(str(part) for part in [self.record, self.type, self.publication])


class RecordParameter(models.Model):
    record = models.ForeignKey(Record, models.CASCADE, related_name='record_parameters')
    parameter = models.ForeignKey(Parameter, models.PROTECT, related_name='record_parameters')
    units = models.CharField(max_length=55)
    position_units = models.CharField(max_length=55)
    description = models.CharField(max_length=255, blank=True)

    min_value = models.FloatField(blank=True, null=True, default=None)
    max_value = models.FloatField(blank=True, null=True, default=None)
    mean_value = models.FloatField(blank=True, null=True, default=None)
    median_value = models.FloatField(blank=True, null=True, default=None)
    max_value_year = models.FloatField(blank=True, null=True, default=None)
    min_value_year = models.FloatField(blank=True, null=True, default=None)
    max_value_position = models.FloatField(blank=True, null=True, default=None)
    min_value_position = models.FloatField(blank=True, null=True, default=None)

    class Meta:
        ordering = ['parameter__name']

    def __str__(self):
        return '{} ({})'.format(self.parameter.name, self.units)
