# Generated by Django 5.1.1 on 2025-01-16 19:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_rename_apply_wholesale_price_on_customer_discount_product_apply_wholesale_price_on_client_discount'),
        ('sales', '0004_alter_saleproduct_product_alter_saleproduct_sale'),
    ]

    operations = [
        migrations.AlterField(
            model_name='saleproduct',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sales', to='products.product'),
        ),
        migrations.AlterField(
            model_name='saleproduct',
            name='sale',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='sales.sale'),
        ),
    ]