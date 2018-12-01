# Generated by Django 2.1.3 on 2018-12-01 18:13

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('strativerse', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='comment',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='attachment',
            name='key',
            field=models.CharField(max_length=55, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9_.-]+$', message='Must only contain alphanumerics, the dash, period, or underscore')]),
        ),
        migrations.AlterField(
            model_name='tag',
            name='comment',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tag',
            name='key',
            field=models.CharField(max_length=55, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9_.-]+$', message='Must only contain alphanumerics, the dash, period, or underscore')]),
        ),
        migrations.AlterField(
            model_name='tag',
            name='value',
            field=models.TextField(blank=True),
        ),
    ]