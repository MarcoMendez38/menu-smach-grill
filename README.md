# Smach & Grill — menú digital

Menú digital para Chile, con precios en pesos chilenos (CLP) y traducciones al español, portugués e inglés. El catálogo está enfocado en hamburguesas, combos, papas, bebidas y postres.

Aplicación web de menú y pedidos con una base de datos SQLite real.

## Ejecutar

Desde esta carpeta:

```bash
python3 server.py
```

### Frontend Angular

El menú público utiliza Angular y se entrega desde el mismo servidor Python para conservar la API y los QR existentes. El código fuente está en [angular-app](./angular-app). Para instalar dependencias y generar la versión que sirve el backend:

```bash
cd angular-app
npm install
npm run build
cd ..
python3 server.py
```

La compilación queda en `angular-app/dist/frontend/browser`. Si esa carpeta existe, `/` sirve automáticamente la aplicación Angular; `/admin` y `/qr` mantienen sus vistas operativas actuales.

Después abrir [http://localhost:8000](http://localhost:8000) en la computadora.

Para que un teléfono pueda acceder al menú, debe estar conectado a la misma red Wi-Fi. Desde el teléfono usar la IP local de la computadora, por ejemplo `http://192.168.1.7:8000`. La IP puede variar; el servidor la muestra al iniciarse.

## Crear el QR

Abrir `/qr` usando la dirección accesible desde el celular:

```text
http://192.168.1.7:8000/qr
```

La página genera un código QR que apunta exactamente a `http://192.168.1.7:8000/`, muestra la URL codificada y permite imprimirlo. El QR debe generarse con la IP de la computadora dentro de la red, no con `localhost` ni `127.0.0.1`, porque esas direcciones solo funcionan en la propia computadora.

Para publicar el menú en Internet se debe usar un dominio o servicio de hosting con HTTPS y generar el QR desde esa URL pública.

## Publicar en Render

El proyecto incluye [render.yaml](./render.yaml), por lo que se puede desplegar sin agregar dependencias:

1. Crear una cuenta en [Render](https://render.com).
2. Subir este proyecto a un repositorio de GitHub.
3. En Render elegir **New → Blueprint** y seleccionar ese repositorio.
4. Render leerá `render.yaml`, ejecutará el servidor y asignará una URL pública HTTPS.
5. Abrir la URL asignada y agregar `/qr`, por ejemplo `https://brasa-miga-menu.onrender.com/qr`.
6. Imprimir ese QR y colocarlo en las mesas.

El QR generado desde `/qr` usará automáticamente la URL pública de Render, por lo que funcionará desde cualquier red y dispositivo.

### Persistencia de pedidos en Render

La aplicación usa SQLite (`menu.db`). En un servicio gratuito, el disco puede ser efímero durante nuevos despliegues o reinicios. Para un restaurante en producción, agregar un disco persistente de Render o migrar las tablas a PostgreSQL antes de recibir pedidos reales. El menú se recrea automáticamente si la base no existe, pero los pedidos anteriores no deben depender del almacenamiento efímero.

La primera ejecución crea automáticamente `menu.db` con las categorías, productos y tablas de pedidos iniciales.

## Flujo disponible

1. El cliente consulta el menú desde la base de datos.
2. Filtra por categoría o busca productos.
3. Agrega productos al carrito y modifica cantidades.
4. Completa nombre, mesa/modalidad y notas.
5. El servidor valida disponibilidad, calcula el total usando los precios de la base de datos y guarda el pedido.
6. Cada pedido conserva sus productos, cantidades, precios históricos, total, estado y fecha.

## API

- `GET /api/menu`: categorías activas y productos disponibles.
- `POST /api/orders`: crea un pedido.
- `GET /api/orders`: lista pedidos para cocina/administración.
- `GET /api/orders/:id`: consulta un pedido con su detalle.
- `PATCH /api/orders/:id`: actualiza el estado (`pending`, `confirmed`, `preparing`, `ready`, `delivered` o `cancelled`).

El catálogo inicial incluye las categorías `Hamburguesas`, `Combos`, `Papas y acompañamientos`, `Bebidas` y `Postres`. Las imágenes de los productos se sirven desde `angular-app/public/products` y se identifican mediante el campo `image` de la respuesta de menú.

## Panel del restaurante

Abrir `/admin` para consultar pedidos, detalle de productos, mesas ocupadas, ventas con pago aprobado, estado de cada orden y minutos estimados restantes. El panel actualiza la información automáticamente cada 10 segundos y permite cambiar el estado de una orden.

Después de enviar un pedido, el cliente recibe un seguimiento en vivo dentro del menú. La tarjeta de seguimiento consulta `/api/orders/:id` cada 10 segundos y muestra el estado (`Recibido`, `Confirmado`, `En preparación`, `Listo para retirar`), una barra de progreso y el tiempo aproximado restante. El tiempo inicial se calcula según la cantidad de productos, con un rango estimado de 15 a 55 minutos.

El pago es una simulación local: una tarjeta de prueba terminada en `4242` se aprueba y una terminada en `0002` se rechaza. No se procesan cobros reales ni se almacenan datos completos de tarjetas.

## Mesas y códigos QR

El restaurante trabaja con seis mesas. Cada mesa tiene un QR diferente generado desde `/qr`:

```text
https://tu-dominio.com/qr
```

Cada QR abre una URL con una credencial de mesa (`mesa` + `token`). El cliente no elige ni escribe su mesa: el servidor valida la credencial y guarda automáticamente `Mesa 1` a `Mesa 6` en el pedido. La vista pública no lista pedidos de otras mesas.

Después de crear un pedido, el servidor devuelve un token privado de seguimiento. El cliente usa ese token para consultar solo su pedido; intentar consultar otro pedido sin su token devuelve `403`.

El flujo del cliente conserva el carrito por mesa en el navegador, muestra la mesa activa en el encabezado, presenta un resumen antes de enviar, evita envíos duplicados mientras procesa el pedido y recupera el seguimiento del último pedido de esa mesa si el cliente recarga la página.

El panel permite filtrar por estado y mesa, ver el detalle de cada orden, consultar el tiempo restante o atraso y actualizar el estado operativo. La información se refresca automáticamente cada 10 segundos.

En producción definir una clave privada para generar las credenciales:

```text
MENU_SECRET=una-clave-larga-y-secreta
```

Debe mantenerse igual mientras los QR estén impresos. Si cambia, hay que regenerar los seis QR.

Ejemplo de creación:

```json
{
  "customer_name": "Martina",
  "table_number": "Mesa 4",
  "notes": "Sin cebolla",
  "items": [
    { "product_id": 4, "quantity": 1 }
  ]
}
```
