const money = cents => `CLP ${new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 }).format(cents / 100)}`;
const statusNames = { pending: "Pendiente", confirmed: "Confirmada", preparing: "En preparación", ready: "Lista", delivered: "Entregada", cancelled: "Cancelada" };
let orders = [];
const list = document.querySelector("#orders-list");
const filter = document.querySelector("#status-filter");
const tableFilter = document.querySelector("#table-filter");

function isOverdue(order) {
  if (["ready", "delivered", "cancelled"].includes(order.status)) return false;
  const elapsed = Math.floor((Date.now() - new Date(order.created_at).getTime()) / 60000);
  return elapsed >= (order.estimated_minutes || 20);
}

function cardClass(order) {
  if (order.status === "delivered") return "order-card card-delivered";
  if (isOverdue(order)) return "order-card card-overdue";
  if (order.status === "pending") return "order-card card-pending";
  return "order-card";
}

async function loadOrders() {
  try {
    const response = await fetch("/api/orders");
    if (!response.ok) throw new Error("No se pudieron cargar las órdenes");
    const data = await response.json();
    orders = data.orders;
    render();
  } catch (error) {
    list.innerHTML = `<div class="empty-orders">${error.message}</div>`;
  }
}

function render() {
  const visible = orders.filter(order => (filter.value === "all" || order.status === filter.value) && (tableFilter.value === "all" || order.table_number === tableFilter.value));
  const active = orders.filter(order => !["delivered", "cancelled"].includes(order.status));
  const preparing = orders.filter(order => ["confirmed", "preparing"].includes(order.status));
  const tables = new Set(active.map(order => order.table_number).filter(table => table && !/llevar/i.test(table)));
  const sales = orders.filter(order => order.payment_status === "approved").reduce((total, order) => total + order.total_cents, 0);
  document.querySelector("#active-count").textContent = active.length;
  document.querySelector("#preparing-count").textContent = preparing.length;
  document.querySelector("#tables-count").textContent = tables.size;
  document.querySelector("#sales-total").textContent = money(sales);
  list.innerHTML = visible.length ? visible.map(order => `
    <article class="${cardClass(order)}">
      <div class="order-top"><div><div class="order-id">Pedido #${order.id} · ${escapeHtml(order.customer_name)}</div><p class="order-meta">${escapeHtml(order.table_number || "Sin mesa")} · ${new Date(order.created_at).toLocaleString("es-CL")}</p></div><span class="order-status status-${order.status}">${statusNames[order.status]}</span></div>
      <div class="order-body"><div class="order-items" id="items-${order.id}">Cargando detalle...</div><div class="order-payment"><strong>${money(order.total_cents)}</strong><span class="payment-${order.payment_status}">${order.payment_status === "approved" ? "Pago aprobado" : order.payment_status === "declined" ? "Pago rechazado" : "Pago pendiente"} · ${order.payment_method}</span>${order.transaction_ref ? `<small>Ref. ${order.transaction_ref}</small>` : ""}<span class="order-remaining">${remainingText(order)}</span></div></div>
      ${order.notes ? `<p class="order-notes"><strong>Notas:</strong> ${escapeHtml(order.notes)}</p>` : ""}
      <div class="order-actions"><label>Actualizar estado <select data-order="${order.id}">${Object.entries(statusNames).map(([value, label]) => `<option value="${value}" ${value === order.status ? "selected" : ""}>${label}</option>`).join("")}</select></label></div>
    </article>
  `).join("") : '<div class="empty-orders">No hay órdenes con este filtro.</div>';
  visible.forEach(loadItems);
  list.querySelectorAll("select[data-order]").forEach(select => select.addEventListener("change", () => updateStatus(Number(select.dataset.order), select.value)));
}

function remainingText(order) {
  if (["ready", "delivered", "cancelled"].includes(order.status)) return order.status === "ready" ? "Listo para entregar" : statusNames[order.status];
  const elapsed = Math.floor((Date.now() - new Date(order.created_at).getTime()) / 60000);
  const remaining = Math.max(0, (order.estimated_minutes || 20) - elapsed);
  return remaining ? `${remaining} min estimados restantes` : "Preparación atrasada";
}

async function loadItems(order) {
  const response = await fetch(`/api/orders/${order.id}`);
  if (!response.ok) return;
  const data = await response.json();
  const target = document.querySelector(`#items-${order.id}`);
  if (target) target.innerHTML = data.items.map(item => `<div><strong>${item.quantity}×</strong> ${escapeHtml(item.product_name)} · ${money(item.subtotal_cents)}</div>`).join("");
}

async function updateStatus(id, status) {
  const response = await fetch(`/api/orders/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
  if (!response.ok) return loadOrders();
  await loadOrders();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character]));
}

filter.addEventListener("change", render);
tableFilter.addEventListener("change", render);
loadOrders();
setInterval(loadOrders, 10000);
