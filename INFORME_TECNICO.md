# Informe técnico — Smach & Grill

## 1. Resumen

Smach & Grill es un sistema web de pedidos para una hamburguesería. El cliente escanea el QR de su mesa, consulta el menú, arma un carrito, confirma el pedido y sigue su estado desde el teléfono. El restaurante administra las órdenes desde un panel web.

La aplicación está publicada en:

- Menú público: <https://menu-smach-grill.onrender.com/>
- Panel del restaurante: <https://menu-smach-grill.onrender.com/admin>
- Generador de QR: <https://menu-smach-grill.onrender.com/qr>
- Health check: <https://menu-smach-grill.onrender.com/health>
- Repositorio: <https://github.com/MarcoMendez38/menu-smach-grill>

## 2. Arquitectura

```text
Celular del cliente
        ↓ HTTPS
Frontend Angular
        ↓ API HTTP/JSON
Backend Python
        ↓
SQLite (menu.db)
```

### Frontend

El menú público está desarrollado con Angular 19, TypeScript, HTML y SCSS. Utiliza componentes standalone y un diseño responsive para teléfonos, tablets y computadores.

- Código principal: `angular-app/src/app/`
- Imágenes: `angular-app/public/products/`
- Build de producción: `angular-app/dist/frontend/browser`

El backend sirve el build Angular desde `/` y conserva las vistas operativas `/admin` y `/qr`.

### Backend

El backend está implementado en `server.py` usando `http.server`, `ThreadingHTTPServer`, SQLite y JSON. Sus responsabilidades son:

- Servir el frontend y las páginas operativas.
- Exponer la API del menú, mesas y pedidos.
- Validar tokens QR.
- Crear y consultar pedidos.
- Actualizar estados.
- Procesar pagos simulados.
- Responder `/health` para Render.

### Base de datos

`menu.db` contiene:

- `categories`: categorías activas y orden de visualización.
- `products`: nombre, descripción, precio, imagen, categoría y disponibilidad.
- `orders`: cliente, mesa, estado, total, pago, token y fechas.
- `order_items`: productos, cantidades, precios históricos y subtotales.

La relación principal es `orders 1:N order_items` y `categories 1:N products`.

## 3. Catálogo

El catálogo inicial está orientado a hamburguesas:

- Hamburguesas: La Clásica, Doble Smash, La BBQ y Veggie Grill.
- Combos: Combo Clásico y Combo Doble Smash.
- Papas y acompañamientos: Papas clásicas y Papas cheddar y tocino.
- Bebidas: Bebida en lata y Limonada de la casa.
- Postres: Brownie con helado y Milkshake de vainilla.

Los precios se almacenan en centavos de CLP para evitar errores de redondeo. El servidor recalcula el total usando los precios de la base de datos, en lugar de confiar en el precio enviado por el navegador.

## 4. Flujo del cliente

1. El cliente escanea el QR de una mesa.
2. Angular lee `mesa` y `token` desde la URL.
3. El cliente filtra o busca productos.
4. Agrega productos al carrito y modifica cantidades.
5. Ingresa nombre, notas y método de pago.
6. Angular envía `POST /api/orders`.
7. El servidor valida mesa, token, productos, disponibilidad y cantidades.
8. El servidor guarda la orden y sus ítems.
9. El cliente recibe el número y token privado del pedido.
10. Angular consulta el estado cada 10 segundos hasta que la orden sea entregada o cancelada.

Si el menú se abre sin un QR válido, el checkout muestra un mensaje visible y no intenta enviar una orden incompleta.

## 5. QR y seguridad de mesas

El restaurante utiliza seis mesas. Cada URL tiene este formato:

```text
https://menu-smach-grill.onrender.com/?mesa=1&token=TOKEN
```

El token se genera con HMAC-SHA256 a partir de `MENU_SECRET` y el identificador de la mesa. El backend compara el token recibido antes de aceptar un pedido. Cambiar solo el número de mesa no permite utilizar otra mesa.

La variable de entorno debe configurarse en Render:

```text
MENU_SECRET=una-clave-larga-y-secreta
```

Debe mantenerse estable mientras los QR estén impresos. Si cambia, se deben regenerar los seis QR desde `/qr`.

## 6. Estados de pedidos

```text
pending → confirmed → preparing → ready → delivered
```

También puede utilizarse `cancelled`. El panel muestra estos estados en español y colorea las tarjetas según su situación:

- Entregadas: verde.
- Atrasadas: rojo.
- Pendientes sin confirmar: blanco.

El cliente visualiza una barra de progreso, el estado y el tiempo estimado. El panel permite filtrar por estado y mesa y actualizar la orden.

## 7. Pagos

El proyecto incorpora pagos simulados para probar el flujo:

- Tarjeta terminada en `4242`: aprobada.
- Tarjeta terminada en `0002`: rechazada.

No se procesan cobros reales ni se almacenan números completos de tarjetas. Para producción se debe integrar Webpay, Transbank, Flow, Mercado Pago o Stripe mediante sus credenciales oficiales.

## 8. API

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/health` | Verificar disponibilidad del servicio |
| `GET` | `/api/menu` | Obtener categorías y productos |
| `GET` | `/api/tables` | Obtener URLs firmadas de las mesas |
| `POST` | `/api/orders` | Crear un pedido |
| `GET` | `/api/orders/{id}` | Consultar un pedido con su token |
| `PATCH` | `/api/orders/{id}/status` | Cambiar el estado operativo |
| `GET` | `/api/admin/orders` | Listar órdenes para el panel |

Las consultas privadas de pedidos requieren el token correspondiente. Un token incorrecto se rechaza con error HTTP `403`.

## 9. Panel del restaurante

El panel está compuesto por `admin.html` y `admin.js`. Permite:

- Ver pedidos recibidos.
- Consultar cliente, mesa, productos y total.
- Ver método y estado del pago.
- Filtrar por mesa y estado.
- Cambiar el estado operativo.
- Consultar pedidos activos, por preparar, mesas ocupadas y ventas aprobadas.
- Actualizar información automáticamente cada 10 segundos.

El panel debe protegerse con autenticación antes de operar con datos reales. La versión actual no implementa todavía usuarios, sesiones ni roles.

## 10. Despliegue en Render

Render obtiene el código desde GitHub y ejecuta:

**Build Command**

```bash
cd angular-app && npm ci && npm run build && cd .. && python3 -m py_compile server.py
```

**Start Command**

```bash
python3 server.py
```

Variables configuradas:

```text
PYTHON_VERSION=3.12.8
MENU_SECRET=<clave privada estable>
```

El servidor escucha en `0.0.0.0` y prioriza la variable `PORT` que entrega Render.

## 11. Operación diaria

1. Imprimir los QR desde `/qr`.
2. Colocar cada QR en su mesa.
3. Abrir `/admin` en el dispositivo del restaurante.
4. Confirmar los pedidos entrantes.
5. Cambiar el pedido a `preparing`, `ready` y `delivered`.
6. Verificar que el cliente reciba el avance en su teléfono.

## 12. Consideraciones de producción

SQLite funciona para pruebas y operaciones pequeñas. Para producción se recomienda migrar a PostgreSQL o usar un disco persistente de Render, porque el almacenamiento local puede ser efímero durante reinicios o despliegues.

También se recomienda implementar:

- Autenticación y autorización del panel.
- PostgreSQL administrado.
- Pasarela de pagos real.
- Registro centralizado de errores.
- Copias de seguridad.
- Dominio propio.
- HTTPS y rotación controlada de secretos.

## 13. Estructura principal

```text
MenuQr/
├── server.py
├── menu.db
├── render.yaml
├── README.md
├── INFORME_TECNICO.md
├── qr.html
├── admin.html
├── admin.js
└── angular-app/
    ├── package.json
    ├── package-lock.json
    ├── angular.json
    ├── public/products/
    └── src/app/
```
