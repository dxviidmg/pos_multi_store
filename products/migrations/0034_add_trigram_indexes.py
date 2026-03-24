from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0033_add_performance_indexes_v2'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name='product',
            index=GinIndex(
                name='product_name_trgm',
                fields=['name'],
                opclasses=['gin_trgm_ops'],
            ),
        ),
        migrations.AddIndex(
            model_name='brand',
            index=GinIndex(
                name='brand_name_trgm',
                fields=['name'],
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]
