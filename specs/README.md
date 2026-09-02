# 📐 SmartVenta — Spec-Driven Development

Este directorio contiene las especificaciones OpenAPI 3.0 del proyecto.

## Filosofía

La spec es la **fuente de verdad**. Todo endpoint nuevo se define aquí primero,
se revisa, y luego se implementa.

## Estructura

```
specs/
├── README.md              ← Este archivo
├── clients.yaml           ← Módulo de clientes y descuentos
├── schemas/               ← Schemas compartidos entre módulos (futuro)
└── (próximos módulos...)
```

## Flujo de trabajo

1. **Spec primero** — Definir el endpoint en el YAML correspondiente
2. **Revisar** — Validar la spec con herramientas o en equipo
3. **Implementar** — Escribir el código que cumpla la spec
4. **Testear** — Verificar que la implementación coincide con el contrato

## Validar specs localmente

```bash
# Instalar spectral (linter de OpenAPI)
npm install -g @stoplight/spectral-cli

# Validar
spectral lint specs/clients.yaml
```

O usar la extensión de VS Code: [OpenAPI Editor](https://marketplace.visualstudio.com/items?itemName=42Crunch.vscode-openapi)

## Convenciones

- Formato: OpenAPI 3.0.3
- Un archivo por módulo Django
- Schemas reutilizables van en `schemas/` cuando se comparten entre módulos
- Nombres de operación: `{recurso}_{acción}` (ej: `client_list`, `discount_create`)
- Seguridad: Token auth global, se hereda en todos los endpoints
