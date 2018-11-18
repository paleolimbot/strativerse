
from pybtex.database import parse_string as parse_bibtex
from pybtex.database import BibliographyData

from django.db import models
from django.contrib.auth.models import User

from .geometry import validate_wkt, wkt_bounds


class GeoModel(models.Model):
    geo_wkt = models.TextField(validators=[validate_wkt, ], blank=True)
    geo_error = models.FloatField(default=0)

    geo_elev = models.FloatField(default=0)
    geo_elev_error = models.FloatField(default=0)

    geo_xmin = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_xmax = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_ymin = models.FloatField(editable=False, blank=True, null=True, default=None)
    geo_ymax = models.FloatField(editable=False, blank=True, null=True, default=None)

    class Meta:
        abstract = True

    def update_bounds(self):
        bounds = wkt_bounds(self.geo_wkt)
        self.geo_xmin = bounds['xmin']
        self.geo_xmax = bounds['xmax']
        self.geo_ymin = bounds['ymin']
        self.geo_ymax = bounds['ymax']


class Feature(GeoModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(
        choices=[
            ('water_body', 'Water Body'),
            ('glacier', 'Glacier'),
            ('bog', 'Bog')
        ],
        max_length=55
    )
    parent = models.ForeignKey('self', on_delete=models.PROTECT, related_name='children')

    def save(self, *args, **kwargs):
        self.update_bounds()
        super().save(*args, **kwargs)


class Person(models.Model):
    given_names = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    contact = models.TextField(blank=True)

    class Meta:
        ordering = ['last_name', 'given_names']

    def __str__(self):
        if self.given_names:
            return ' '.join((self.given_names, self.last_name))
        else:
            return self.last_name


class Alias(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='aliases')
    alias = models.CharField(max_length=255)


class Affiliation(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='affiliations')
    order = models.IntegerField(default=1)
    text = models.TextField()

    class Meta:
        ordering = ['person__last_name', 'person__given_names', 'order', ]

    def __str__(self):
        return self.text


class Publication(models.Model):
    slug = models.CharField(max_length=55, unique=True)
    name = models.CharField(max_length=255)
    biblatex = models.TextField()
    doi = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)
    pdf = models.FileField(upload_to='publications')

    @staticmethod
    def import_bibtex(text):
        bib = parse_bibtex(text, bib_format='bibtex')
        items = []
        for key, entry in bib.entries.items():
            # check for key already in database (skip if it is?)
            try:
                items.append(Publication.objects.get(slug=key))
                continue
            except Publication.DoesNotExist:
                pass

            # create publication
            pub = Publication.objects.create(
                slug=key,
                name=entry.fields['title'].replace('{', '').replace('}', '') if 'title' in entry.fields else 'Untitled',
                biblatex=BibliographyData({key: entry}).to_string('bibtex'),
                doi=entry.fields['doi'] if 'doi' in entry.fields else '',
                url=entry.fields['url'] if 'url' in entry.fields else ''
            )

            # get or create people
            for role, person_list in entry.persons.items():
                for i, p in enumerate(person_list):
                    try:
                        person = Alias.objects.get(alias=str(p))
                    except Alias.DoesNotExist:
                        person = Person.objects.create(
                            given_names=' '.join(p.bibtex_first_names).replace('{', '').replace('}', '').strip(),
                            last_name=' '.join(p.last_names).replace('{', '').replace('}', '').strip()
                        )
                        Alias.objects.create(person=person, alias=str(p))
                    Authorship.objects.create(
                        publication=pub,
                        person=person,
                        role=role,
                        order=i
                    )

            items.append(pub)

        return items

    def __str__(self):
        return '%s (%s)' % (
            self.name,
            self.authorships.first().person if self.authorships.all().count() else '<authorless>'
        )


class Authorship(models.Model):
    publication = models.ForeignKey(Publication, models.CASCADE, related_name='authorships')
    person = models.ForeignKey(Person, models.CASCADE, related_name='authorships')
    role = models.CharField(max_length=55)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['role', 'order']


class Record(GeoModel):
    name = models.CharField(max_length=255)
    date = models.DateField()
    description = models.TextField(blank=True)
    type = models.CharField(
        choices=[
            ('sediment_core', 'Sediment Core'),
            ('ice_core', 'Ice Core'),
            ('peat_core', 'Peat Core')
        ],
        max_length=55
    )
    publications = models.ManyToManyField(Publication, related_name='records')

    def save(self, *args, **kwargs):
        self.update_bounds()
        super().save(*args, **kwargs)
