# Generated by Django 5.1.1 on 2024-11-01 12:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_producttransfer_transfer_datetime'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='producttransfer',
            name='is_delivered',
        ),
    ]