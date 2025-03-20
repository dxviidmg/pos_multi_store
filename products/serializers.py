from rest_framework import serializers
from .models import (
    Product,
    StoreProduct,
    Transfer,
    Store,
    Brand,
    StoreProductLog,
    CashFlow,
)
from django.core.exceptions import ValidationError
from sales.cash_summary_utils import calculate_cash_summary
from datetime import datetime, date


class BrandSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    def get_product_count(self, obj):
        return obj.count_products()

    class Meta:
        model = Brand
        exclude = ["tenant"]



class ProductSearchSerializer(serializers.ModelSerializer):
    brand_name = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()

    def get_brand_name(self, obj):
        return obj.brand.name
    
    def get_prices(self, obj):
        return {
            "unit_price": obj.unit_price,
            "wholesale_price": obj.wholesale_price,
            "min_wholesale_quantity": obj.min_wholesale_quantity,
            "apply_wholesale": obj.apply_wholesale(),
            "wholesale_price_on_client_discount": obj.wholesale_price_on_client_discount,
        }
    
    class Meta:
        model = Product
        fields = ["id", "code", "brand_name", "name", "prices", "image"]    


class ProductSerializer(serializers.ModelSerializer):
    brand_name = serializers.SerializerMethodField()
    apply_wholesale = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    def get_brand_name(self, obj):
        return obj.brand.name

    def get_apply_wholesale(self, obj):
        return obj.apply_wholesale()
    
    def get_stock(self, obj):
        return obj.get_stock()

    class Meta:
        model = Product
        fields = "__all__"

    def validate(self, data):
        request = self.context.get("request")
        method = request.method if request else None

        if method == "POST":
            if Product.objects.filter(
                code=data["code"], brand__tenant=data["brand"].tenant
            ).exists():
                raise ValidationError(
                    {"code": "product with this code already exists."}
                )

        return data
    
class StoreProductBaseSerializer(serializers.ModelSerializer):
    product =  ProductSearchSerializer(read_only=True)

    class Meta:
        model = StoreProduct
        fields = "__all__"


class StoreProductSerializer(StoreProductBaseSerializer):
    available_stock = serializers.SerializerMethodField()
    reserved_stock = serializers.SerializerMethodField()
    stock_in_other_stores = serializers.SerializerMethodField()

    def get_product_description(self, obj):
        return obj.product.get_description()

    def get_available_stock(self, obj):
        return obj.calculate_available_stock()

    def get_reserved_stock(self, obj):
        return obj.calculate_reserved_stock()



    def get_stock_in_other_stores(self, obj):
        # Optimize by pre-filtering and reducing unnecessary calculations
        return [
            {
                "store_id": str(sp.store.id),
                "store_name": str(sp.store),
                "available_stock": sp.calculate_available_stock(),
            }
            for sp in StoreProduct.objects.filter(product=obj.product)
            .exclude(id=obj.id)
            .exclude(stock=0)
            if sp.calculate_available_stock() > 0
        ]


class StoreProductLogSerializer(serializers.ModelSerializer):

    description = serializers.SerializerMethodField()
    difference = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()

    def get_description(self, obj):
        return obj.get_description()

    def get_difference(self, obj):
        return obj.calculate_difference()

    def get_user_username(self, obj):
        return obj.user.username

    class Meta:
        model = StoreProductLog
        fields = "__all__"


class StoreProductLogSerializer2(StoreProductLogSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, obj):
        return ProductSerializer(obj.store_product.product).data


class TransferSerializer(serializers.ModelSerializer):
    product_code = serializers.SerializerMethodField()
    product_description = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_product_code(self, obj):
        return obj.product.code

    def get_product_description(self, obj):
        return obj.product.get_description()

    def get_description(self, obj):
        store = self.context["request"].store
        if store == obj.origin_store:
            return "Le proveere este producto a " + obj.destination_store.__str__()
        elif store == obj.destination_store:
            return "Le solicite este producto a " + obj.origin_store.__str__()
        return "No tengo gerencia entre traspaso"

    class Meta:
        model = Transfer
        fields = "__all__"


class StoreSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    store_type_display = serializers.SerializerMethodField()
    url_printer = serializers.SerializerMethodField()
    products_count = serializers.IntegerField(source='count_products', read_only=True)

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_store_type_display(self, obj):
        return obj.get_store_type_display()

    def get_url_printer(self, obj):
        return obj.get_url_printer()
    
    class Meta:
        model = Store
        fields = "__all__"


class StoreCashSummarySerializer(StoreSerializer):
    cash_summary = serializers.SerializerMethodField()    

    def get_cash_summary(self, obj):
        start_date_str = self.context.get("start_date")
        end_date_str = self.context.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        return calculate_cash_summary(obj, None, start_date, end_date)




class CashFlowSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()

    def get_transaction_type_display(self, obj):
        return obj.get_transaction_type_display()

    def get_user_username(self, obj):
        return obj.user.username

    class Meta:
        model = CashFlow
        fields = "__all__"


class CashFlowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashFlow
        fields = ["concept", "amount", "transaction_type"]
