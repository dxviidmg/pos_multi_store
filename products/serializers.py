from datetime import date, datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework import serializers

from sales.cash_summary_utils import (
    calculate_cash_summary,
    calculate_cash_summary_by_department,
    calculate_total_sales_by_seller,
)
from .models import (
    Brand,
    CashFlow,
    Department,
    Distribution,
    Product,
    Store,
    StockUpdateRequest,
    StoreProduct,
    StoreWorker,
    Transfer,
)


class BrandSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        exclude = ["tenant"]
    
    def get_product_count(self, obj):
        store = self.context.get('store')
        audit = self.context.get('audit', False)
        
        if audit and store:
            return obj.products.filter(
                product_stores__store=store,
                product_stores__requires_stock_verification=True
            ).distinct().count()
        return obj.count_products()

class DepartmentSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        exclude = ["tenant"]
    
    def get_product_count(self, obj):
        store = self.context.get('store')
        audit = self.context.get('audit', False)
        
        if audit and store:
            return obj.products.filter(
                product_stores__store=store,
                product_stores__requires_stock_verification=True
            ).distinct().count()
        return obj.count_products()


class ProductSearchSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    prices = serializers.SerializerMethodField()

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
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    department_name = serializers.SerializerMethodField()
    apply_wholesale = serializers.SerializerMethodField()
    stock = serializers.IntegerField(source='get_stock', read_only=True)

    def get_department_name(self, obj):
        return obj.department.name if obj.department else ''

    def get_apply_wholesale(self, obj):
        return obj.apply_wholesale()

    class Meta:
        model = Product
        fields = "__all__"

    def validate(self, data):
        request = self.context.get("request")
        if request and request.method == "POST":
            if Product.objects.filter(
                code=data["code"], brand__tenant=data["brand"].tenant
            ).exists():
                raise ValidationError(
                    {"code": "product with this code already exists."}
                )
        return data


class StoreBaseSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    store_type_display = serializers.CharField(source='get_store_type_display', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    workers_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Store
        fields = "__all__"


class StoreProductBaseSerializer(serializers.ModelSerializer):
    product = ProductSearchSerializer(read_only=True)

    class Meta:
        model = StoreProduct
        fields = "__all__"


class StoreProductCodeSerializer(StoreProductBaseSerializer):
    available_stock = serializers.IntegerField(read_only=True)
    reserved_stock = serializers.IntegerField(read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)


class StoreProductSerializer(StoreProductBaseSerializer):
    available_stock = serializers.IntegerField(read_only=True)
    reserved_stock = serializers.IntegerField(read_only=True)
    store = StoreBaseSerializer(read_only=True)


class ProductForStockSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)

    class Meta:
        model = Product
        fields = ["id", "code", "brand_name", "name", "image"]


class StoreProductForStockSerializer(serializers.ModelSerializer):
    product = ProductForStockSerializer(read_only=True)

    class Meta:
        model = StoreProduct
        fields = "__all__"


class TransferSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_description = serializers.CharField(source='product.get_description', read_only=True)
    editable_product_max_stock = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_description(self, obj):
        store = self.context["request"].store
        if store == obj.destination_store:
            return "Le solicite este producto a " + str(obj.origin_store)
        elif store == obj.origin_store:
            return "Le proveere este producto a " + str(obj.destination_store)
        return "No tengo gerencia entre traspaso"

    def get_editable_product_max_stock(self, obj):
        store_product = StoreProduct.objects.get(product=obj.product, store=obj.origin_store)
        return obj.quantity + store_product.calculate_available_stock()

    class Meta:
        model = Transfer
        fields = "__all__"


class StoreSerializer(StoreBaseSerializer):
    printer = serializers.SerializerMethodField()
    products_count = serializers.IntegerField(source='count_products', read_only=True)
    workers_count = serializers.IntegerField(read_only=True)
    pending_transfers_count = serializers.SerializerMethodField()

    def get_printer(self, obj):
        return obj.get_store_printer()

    def get_pending_transfers_count(self, obj):
        return obj.transfers_from.filter(transfer_datetime=None).count() + obj.transfers_to.filter(transfer_datetime=None).count()

    class Meta:
        model = Store
        fields = "__all__"


class StoreCashSummarySerializer(StoreSerializer):
    cash_summary = serializers.SerializerMethodField()

    def get_cash_summary(self, obj):
        start_date_str = self.context.get("start_date")
        end_date_str = self.context.get("end_date")
        department_id = self.context.get("department_id", None)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else date.today()
        if department_id:
            return calculate_cash_summary_by_department(obj, None, start_date, end_date, department_id)
        return calculate_cash_summary(obj, None, start_date, end_date)


class CashFlowSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = CashFlow
        fields = "__all__"


class CashFlowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashFlow
        fields = ["concept", "amount", "transaction_type"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['password']


class StoreWorkerSerializer(serializers.ModelSerializer):
    store = serializers.PrimaryKeyRelatedField(queryset=Store.objects.all(), write_only=True, required=False)
    store_detail = StoreSerializer(source='store', read_only=True)
    worker = UserSerializer()
    total_sales = serializers.SerializerMethodField(read_only=True)

    def get_total_sales(self, obj):
        start_date_str = self.context.get("start_date")
        end_date_str = self.context.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else date.today()

        if isinstance(obj, dict):
            user = User.objects.get(username=obj['worker']['username'])
            return calculate_total_sales_by_seller(user, start_date, end_date)
        return calculate_total_sales_by_seller(obj.worker, start_date, end_date)

    class Meta:
        model = StoreWorker
        fields = "__all__"


class StoreProductAuditSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.get_description', read_only=True)
    store_name = serializers.CharField(source='store.get_full_name', read_only=True)
    current_stock = serializers.IntegerField(source='stock', read_only=True)
    last_log_stock = serializers.SerializerMethodField()

    class Meta:
        model = StoreProduct
        fields = ["id", "product_code", "product_name", "store_name", "current_stock", "last_log_stock"]

    def get_last_log_stock(self, obj):
        last_log = obj.store_product_logs.order_by('-id').values('updated_stock').first()
        return last_log['updated_stock'] if last_log else None


class DistributionSerializer(serializers.ModelSerializer):
    origin_store = serializers.PrimaryKeyRelatedField(read_only=True)
    transfers = TransferSerializer(read_only=True, many=True)
    description = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Distribution
        fields = "__all__"


class StockUpdateRequestSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    product_code = serializers.CharField(source='store_product.product.code', read_only=True)
    product_name = serializers.CharField(source='store_product.product.get_description', read_only=True)
    store_name = serializers.CharField(source='store_product.store.get_full_name', read_only=True)

    class Meta:
        model = StockUpdateRequest
        fields = [
            'id', 'store_product', 'product_code', 'product_name', 'store_name',
            'requested_by', 'requested_by_username',
            'requested_stock', 'applied', 'created_at',
        ]
        read_only_fields = ['requested_by', 'applied']
