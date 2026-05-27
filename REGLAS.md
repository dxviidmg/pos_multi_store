# Reglas de contexto

- **Log previo**: El `StoreProductLog` con `pk` inmediatamente menor del mismo `store_product`.
  ```python
  StoreProductLog.objects.filter(store_product=self.store_product, pk__lt=self.pk).order_by("-pk").only("updated_stock").first()
  ```
