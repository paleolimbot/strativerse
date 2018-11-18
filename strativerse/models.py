
from pybtex.database import parse_string as parse_bibtex
from pybtex.database import BibliographyData

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import RegexValidator, ValidationError
from django.db import models
from django.contrib.auth.models import User
import reversion

from .geometry import validate_wkt, wkt_bounds, wkt_geometry_type


class Tag(models.Model):
    type = models.CharField(max_length=55, default='tag')
    key = models.CharField(max_length=55, validators=[
        RegexValidator(r'^[A-Za-z0-9_]+$', message='Must only contain alphanumerics or the underscore')
    ])
    value = models.CharField(max_length=255)
    comment = models.CharField(max_length=512)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id', 'type', 'key']
        ordering = ['key']

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
        ordering = ['key']

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


class TaggedModel(models.Model):
    tags = GenericRelation(Tag)

    class Meta:
        abstract = True


class AttachableModel(models.Model):
    attachments = GenericRelation(Attachment)

    class Meta:
        abstract = True


class Feature(TaggedModel, AttachableModel, RecursiveModel, GeoModel):
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

    def save(self, *args, **kwargs):
        self.cache_bounds()
        self.cache_recursive_depth()
        super().save(*args, **kwargs)

    def __str__(self):
        return '%s <%s %s>' % (self.name, self.type, self.pk)


class Person(TaggedModel, AttachableModel):
    given_names = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)
    suffix = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name_plural = 'people'
        ordering = ['last_name', 'given_names']

    def __str__(self):
        if self.given_names:
            return ' '.join((self.given_names, self.last_name))
        else:
            return self.last_name


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


def validate_biblatex(value):
    try:
        bib = parse_bibtex(value, bib_format='bibtex')
        if len(bib.entries) != 1:
            raise ValidationError('Text must contain exactly one biblatex entry')
    except Exception as e:
        raise ValidationError('Biblatex parse error: "%s"' % e)


class Publication(TaggedModel, AttachableModel):
    slug = models.CharField(max_length=55, unique=True)
    title = models.CharField(max_length=255)
    biblatex = models.TextField(validators=[validate_biblatex, ])
    doi = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)
    year = models.IntegerField()

    class Meta:
        ordering = ['year', 'slug']

    def update_from_bibtex(self, update_authors=False):
        key = self.slug
        bib = parse_bibtex(self.biblatex, 'bibtex')
        entry = bib.entries[list(bib.entries.keys())[0]]

        # create publication
        if 'year' in entry.fields:
            year = int(entry.fields['year'])
        elif 'date' in entry.fields:
            year = int(entry.fields['date'].strip()[:4])
        else:
            raise ValidationError('No year in entry "%s"' % key)

        self.title = entry.fields['title'].replace('{', '').replace('}', '') if 'title' in entry.fields else 'Untitled'
        self.doi = entry.fields['doi'].replace('\\_', '_') if 'doi' in entry.fields else ''
        self.url = entry.fields['url'].replace('\\_', '_') if 'url' in entry.fields else ''
        self.year = year

        if update_authors:
            if not self.pk:
                self.save()

            for authorship in self.authorships.all():
                authorship.delete()

            for role, person_list in entry.persons.items():
                for i, p in enumerate(person_list):
                    try:
                        person = Alias.objects.get(alias=str(p)).person
                    except Alias.DoesNotExist:
                        person = Person.objects.create(
                            given_names=' '.join(p.bibtex_first_names).replace('{', '').replace('}', '').strip(),
                            last_name=' '.join(p.last_names).replace('{', '').replace('}', '').strip()
                        )
                        Alias.objects.create(person=person, alias=str(p))

                    Authorship.objects.create(
                        publication=self,
                        person=person,
                        role=role,
                        order=i
                    )

    @staticmethod
    def import_biblatex(text, update_authors=True, user=None):
        with reversion.create_revision(atomic=True):
            bib = parse_bibtex(text, bib_format='bibtex')
            items = []
            for key, entry in bib.entries.items():
                # check for key already in database (update everything except authorship if it is)
                try:
                    pub = Publication.objects.get(slug=key)
                except Publication.DoesNotExist:
                    pub = Publication(slug=key, biblatex=BibliographyData({key: entry}).to_string('bibtex'))

                pub.update_from_bibtex(update_authors=update_authors)
                pub.save()

                items.append(pub)

            reversion.set_comment('biblatex import [%s items]' % len(items))
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
        return '%s: "%s"' % (self.author_date_key(), title)


class Authorship(models.Model):
    publication = models.ForeignKey(Publication, models.CASCADE, related_name='authorships')
    person = models.ForeignKey(Person, models.PROTECT, related_name='authorships')
    role = models.CharField(max_length=55)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['role', 'order']

    def __str__(self):
        return '%s (%s)' % (self.person, self.role)


class Record(GeoModel, TaggedModel, AttachableModel):
    name = models.CharField(max_length=255)
    date = models.DateField()
    description = models.TextField(blank=True)
    type = models.CharField(
        choices=[
            ('sediment_core', 'Sediment Core'),
            ('ice_core', 'Ice Core'),
            ('peat_core', 'Peat Core'),
            ('water_sample', 'Water Sample'),
            ('section', 'Section')
        ],
        max_length=55
    )

    class Meta:
        ordering = ['date']

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
            return '%s (%s)' % (author_text, self.date.year)
        else:
            return '%s %s' % (author_text, self.date.year)

    def __str__(self):
        return '%s: %s' % (self.author_date_key(), self.name)


class RecordFeatureRelation(models.Model):
    record = models.ForeignKey(Record, models.CASCADE, related_name='feature_relation')
    feature = models.ForeignKey(Feature, models.CASCADE, related_name='record_relation')
    relationship = models.CharField(max_length=55, default='intersects', choices=[
        ('intersects', 'Intersects')
    ])


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

    class Meta:
        ordering = ['publication__date']
