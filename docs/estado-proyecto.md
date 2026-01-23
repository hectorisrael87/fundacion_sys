# 📘 Documentación Técnica  
## Sistema Web Administrativo – Fundación  
**Módulos: Cuadros Comparativos y Órdenes de Pago**

---

## 1. Descripción general

El Sistema Web Administrativo de la Fundación es una plataforma desarrollada para **gestionar el proceso completo de compras y pagos**, desde la cotización inicial hasta la generación y aprobación de órdenes de pago.

El sistema centraliza la información, define flujos claros de aprobación y mantiene trazabilidad de usuarios, montos y decisiones administrativas.

---

## 2. Problema que resuelve

Antes del sistema, la Fundación enfrentaba:

- Cotizaciones manejadas de forma manual o dispersa
- Falta de comparación clara entre proveedores
- Escaso control de aprobaciones
- Dificultad para manejar pagos parciales (anticipos y complementos)
- Falta de trazabilidad de quién crea, revisa y aprueba

El sistema resuelve estos problemas mediante flujos estructurados, control de roles y documentación automática.

---

## 3. Tecnologías utilizadas

### Backend
- Python 3.12
- Django 5.x
- Django ORM
- num2words (conversión de montos a letras)

### Frontend
- HTML (Django Templates)
- CSS propio (`static/css/app.css`)
- Flexbox para layout (sin frameworks externos)

### Base de datos
- PostgreSQL

### Infraestructura
- Docker
- Docker Compose

---

## 4. Arquitectura general

Arquitectura **monolítica modular**, basada en Django.

### Capas del sistema

- **Presentación**
  - Templates HTML
  - Layout base con Topbar + Sidebar
  - Vistas de detalle e impresión

- **Lógica de negocio**
  - Views Django
  - Reglas de flujo y permisos
  - Cálculos financieros

- **Persistencia**
  - Modelos Django
  - Relaciones entre cuadros, proveedores y órdenes

- **Seguridad**
  - Autenticación Django
  - Roles y permisos personalizados

---

## 5. Módulos creados

---

### 5.1 Procurement – Cuadros Comparativos

#### Funcionalidades
- Creación y edición de cuadros comparativos
- Gestión de productos (ítems)
- Gestión de proveedores
- Matriz de precios por proveedor
- Cálculo automático:
  - Totales por proveedor
  - Total general
- Selección de proveedor con motivo
- Flujo de estados:
  - BORRADOR
  - EN_REVISION
  - APROBADO
- Registro de usuarios:
  - Creado por
  - Revisado por
  - Fecha de revisión
- Generación de Órdenes de Pago
- Visualización de órdenes asociadas

---

### 5.2 Payments – Órdenes de Pago

#### Funcionalidades
- Generación automática desde Cuadro Comparativo
- Una orden por proveedor
- Vista única para ver y editar (según estado)
- Gestión de pagos:
  - Pago total
  - Pago parcial (anticipo)
  - Pago complementario
- Cálculos:
  - Total por ítems
  - Monto solicitado
  - Monto restante
- Conversión del monto a letras
- Flujo de aprobación:
  - Enviar a revisión
  - Aprobar
  - Bloqueo de edición tras aprobación
- Registro de:
  - Creado por
  - Aprobado por
  - Fecha de aprobación
- Vista de impresión con firmas

---

### 5.3 Core – Seguridad y utilidades

#### Incluye
- Roles de usuario:
  - Creador
  - Revisor
  - Administrador
- Control de acceso por vista y acción
- Utilidades compartidas:
  - Conversión de montos a letras

---

## 6. Flujo del sistema

1. Usuario creador genera un Cuadro Comparativo
2. Se agregan productos y proveedores
3. Se cargan precios y se comparan totales
4. Se selecciona proveedor con motivo
5. El cuadro se envía a revisión
6. Usuario revisor aprueba el cuadro
7. Se generan Órdenes de Pago
8. La orden puede ser:
   - Total
   - Parcial (anticipo)
9. Si es parcial, se genera complemento
10. La orden se revisa y aprueba
11. Se imprime la documentación final

---

## 7. Estado actual del sistema

### Implementado
- Cuadros Comparativos completos
- Matriz de precios funcional
- Flujo de revisión y aprobación
- Generación de Órdenes de Pago
- Pagos parciales y complementarios
- Control de permisos por usuario
- Layout con sidebar y topbar
- Impresión de Órdenes de Pago con firmas
- Migraciones aplicadas correctamente

### En ajuste
- Refinamiento visual del Cuadro Comparativo
- Ajustes de UX y estilos

---

## 8. Pendientes y mejoras futuras

### Funcionales
- Impresión del Cuadro Comparativo
- Historial de acciones (auditoría)
- Adjuntar documentos (cotizaciones, facturas)
- Búsqueda y filtros avanzados

### Visuales
- Mejora de estilos y jerarquía visual
- Indicadores de estado más claros

### Escalabilidad
- Dashboard administrativo
- Reportes exportables (PDF / Excel)
- Nuevos módulos administrativos

---

## 9. Conclusión

El sistema cubre de forma integral el proceso de compras y pagos de la Fundación, asegurando control, trazabilidad y orden administrativo, y deja una base sólida para futuras ampliaciones.

---
