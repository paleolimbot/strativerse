# Generated by Django 2.1.3 on 2018-11-18 02:06

from django.db import migrations, models
import django.db.models.deletion
import strativerse.geometry


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Affiliation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=1)),
                ('text', models.TextField()),
            ],
            options={
                'ordering': ['person__last_name', 'person__given_names', 'order'],
            },
        ),
        migrations.CreateModel(
            name='Alias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alias', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Authorship',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=55)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['role', 'order'],
            },
        ),
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geo_wkt', models.TextField(blank=True, validators=[strativerse.geometry.validate_wkt])),
                ('geo_error', models.FloatField(default=0)),
                ('geo_elev', models.FloatField(default=0)),
                ('geo_elev_error', models.FloatField(default=0)),
                ('geo_xmin', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_xmax', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_ymin', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_ymax', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('type', models.CharField(choices=[('water_body', 'Water Body'), ('glacier', 'Glacier'), ('bog', 'Bog')], max_length=55)),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='children', to='strativerse.Feature')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('given_names', models.CharField(blank=True, max_length=255)),
                ('last_name', models.CharField(max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('contact', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['last_name', 'given_names'],
            },
        ),
        migrations.CreateModel(
            name='Publication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(max_length=55, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('biblatex', models.TextField()),
                ('doi', models.CharField(blank=True, max_length=255)),
                ('url', models.URLField(blank=True)),
                ('pdf', models.FileField(upload_to='publications')),
            ],
        ),
        migrations.CreateModel(
            name='Record',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geo_wkt', models.TextField(blank=True, validators=[strativerse.geometry.validate_wkt])),
                ('geo_error', models.FloatField(default=0)),
                ('geo_elev', models.FloatField(default=0)),
                ('geo_elev_error', models.FloatField(default=0)),
                ('geo_xmin', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_xmax', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_ymin', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('geo_ymax', models.FloatField(blank=True, default=None, editable=False, null=True)),
                ('name', models.CharField(max_length=255)),
                ('date', models.DateField()),
                ('description', models.TextField(blank=True)),
                ('type', models.CharField(choices=[('sediment_core', 'Sediment Core'), ('ice_core', 'Ice Core'), ('peat_core', 'Peat Core')], max_length=55)),
                ('publications', models.ManyToManyField(related_name='records', to='strativerse.Publication')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='authorship',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorships', to='strativerse.Person'),
        ),
        migrations.AddField(
            model_name='authorship',
            name='publication',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorships', to='strativerse.Publication'),
        ),
        migrations.AddField(
            model_name='alias',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='strativerse.Person'),
        ),
        migrations.AddField(
            model_name='affiliation',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='affiliations', to='strativerse.Person'),
        ),
    ]
