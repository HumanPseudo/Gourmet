# 🐱 Roadmap: Gourmet → SIESA

## Fase 1 — POS Completo (2-3 semanas)

Funcionalidades POS que SIESA tiene y Gourmet necesita para ser competitivo:

### 1.1 División de cuentas ✅

- [x] Split de cuenta por items o por porcentaje
- [x] Múltiples pagos por mesa (efectivo, tarjeta, QR)
- [x] UI para seleccionar qué items van en cada cuenta

### 1.2 Planos de mesa visual ✅

- [x] Editor drag-and-drop de layouts de restaurante
- [x] Vista de piso con mesas coloreadas (libre/ocupada/reservada)
- [x] Click en mesa → ver orden activa
- [x] Asignar mesas a meseros

### 1.3 Reservas

- [x] CRUD de reservas (fecha, hora, personas, mesa)
- [x] Vista calendario de reservas
- [ ] Recordatorios automáticos
- [ ] Link público para reservas online

### 1.4 Autogestión (QR por mesa) ✅

- [x] QR único por mesa que abre menú en el celular
- [x] Cliente ve menú, hace pedido, paga desde su celular
- [x] Pedido llega directo a la cocina (KDS)
- [x] Sin app descargable, todo web

### 1.5 Menú mejorado

- [ ] Fotos de platos
- [ ] Variantes/complementos (ej: "papas o arroz", "término de cocción")
- [ ] Menú por día/semana (specials)
- [ ] Disponibilidad en tiempo real (agotado)

---

## Fase 2 — Gestión de Negocio (2-3 semanas)

### 2.1 Reportes y Dashboard

- [ ] Dashboard principal: ventas del día, semana, mes
- [ ] Top 10 platos más vendidos
- [ ] Ventas por mesero
- [ ] Ventas por categoría
- [ ] Horas pico
- [ ] Margen de ganancia por plato
- [ ] Exportar a Excel/PDF

### 2.2 Multi-sucursal

- [ ] Modelo Company/Sucursal
- [ ] Datos aislados por sucursal
- [ ] Vista consolidada (todas las sucursales)
- [ ] Permisos por sucursal
- [ ] Menú compartido o por sucursal

### 2.3 Clientes y Fidelización

- [ ] Modelo Cliente (nombre, teléfono, email, dirección)
- [ ] Historial de pedidos por cliente
- [ ] Puntos de fidelidad (configurable)
- [ ] Clientes frecuentes (top spenders)
- [ ] Notas sobre preferencias/alergias

### 2.4 Promociones y Descuentos

- [ ] Descuentos por porcentaje o monto fijo
- [ ] Happy hour (descuento por horario)
- [ ] Descuento por día de la semana
- [ ] Cupones (código de descuento)
- [ ] 2x1,组合 combos
- [ ] Descuento por cliente frecuente

---

## Fase 3 — Back Office (2-3 semanas)

### 3.1 Compras y Proveedores

- [ ] Modelo Proveedor (nombre, contacto, NIT)
- [ ] Órdenes de compra
- [ ] Recepción de mercancía
- [ ] Historial de compras por proveedor
- [ ] Costo promedio de ingredientes

### 3.2 Costos y Recetas mejorado

- [ ] Costo real por plato (ingredientes + mano de obra)
- [ ] Margen de ganancia por plato
- [ ] Alerta cuando el costo sube
- [ ] Sugerencia de precio de venta
- [ ] Waste tracking (merma)

### 3.3 Nómina básica

- [ ] Modelo Empleado (mesero, cocinero, cajero)
- [ ] Turnos y horarios
- [ ] Registro de horas trabajadas
- [ ] Liquidación básica (salario + horas extra)
- [ ] Propinas separadas

### 3.4 Cuentas por cobrar/pagar

- [ ] Facturación a crédito (clientes frecuentes)
- [ ] Cuentas por pagar a proveedores
- [ ] Recordatorios de pago
- [ ] Estado de cuenta

---

## Fase 4 — Integraciones (1-2 semanas)

### 4.1 Canales de venta

- [ ] Pedidos por WhatsApp (bot básico)
- [ ] Pedidos por Instagram DM
- [ ] Integración con Rappi/DiDi (API)
- [ ] Link de pedidos para redes sociales

### 4.2 Pagos

- [ ] QR Nequi/Daviplata
- [ ] Pasarela de pago (Stripe/MercadoPago)
- [ ] Pago con tarjeta (terminal física)
- [ ] QR QR Code para transferencia

### 4.3 Hardware

- [ ] Impresora de recibos (térmica)
- [ ] Pantalla de cocina (KDS mejorado)
- [ ] Display para mostrar pedidos en cola

---

## Resumen visual

```text
FASE 1: POS Completo         →  Competitivo con SIESA
FASE 2: Gestión de Negocio   →  Inteligencia de negocio
FASE 3: Back Office          →  Control financiero
FASE 4: Integraciones        →  Omnicanal
```

**Tiempo estimado total:** 8-11 semanas

## Prioridad del usuario

¿Por dónde empezar? Opciones:

1. Fase 1 (lo más urgente para competir)
2. Fase 2 (lo que más valor da al negocio)
3. Lo que tú creas mejor
