# Generated by Django 5.1.1 on 2025-02-04 18:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_alter_printer_store'),
    ]

    operations = [
        migrations.RenameField(
            model_name='printer',
            old_name='connection',
            new_name='connection_type',
        ),
    ]
