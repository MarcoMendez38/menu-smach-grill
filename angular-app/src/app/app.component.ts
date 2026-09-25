import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Product { id: number; name: string; description: string; price_cents: number; emoji: string; image: string; vegetarian: number; category: string; }
interface CartItem { product: Product; quantity: number; }
interface Category { name: string; }
interface TrackingOrder {
  id: number;
  status: string;
  estimated_minutes?: number;
  access_token: string;
  items?: unknown[];
}
interface MenuResponse { products: Product[]; categories: Category[]; }
interface OrderResponse { order: Omit<TrackingOrder, 'access_token'>; items: unknown[]; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit, OnDestroy {
  products: Product[] = [];
  categories: string[] = ['Todos'];
  activeCategory = 'Todos';
  searchTerm = '';
  cart: CartItem[] = [];
  cartOpen = false;
  checkoutOpen = false;
  loading = true;
  error = '';
  tableNumber = new URLSearchParams(location.search).get('mesa') || '';
  tableToken = new URLSearchParams(location.search).get('token') || '';
  customerName = '';
  notes = '';
  paymentMethod = 'cash';
  paymentToken = '';
  formError = '';
  tracking: TrackingOrder | null = null;
  private trackingTimer?: ReturnType<typeof setInterval>;
  private readonly money = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 });

  async ngOnInit() {
    this.restoreCart();
    this.restoreTracking();
    try {
      const response = await fetch('/api/menu');
      if (!response.ok) throw new Error();
      const data: MenuResponse = await response.json();
      this.products = data.products;
      this.categories = ['Todos', ...data.categories.map(item => item.name)];
    } catch {
      this.error = 'No pudimos cargar el menú. Verifica que el servidor esté funcionando.';
    } finally {
      this.loading = false;
    }
  }

  ngOnDestroy() {
    if (this.trackingTimer) clearInterval(this.trackingTimer);
  }

  get filteredProducts() {
    const term = this.searchTerm.trim().toLowerCase();
    return this.products.filter(product =>
      (this.activeCategory === 'Todos' || product.category === this.activeCategory) &&
      (!term || `${product.name} ${product.description}`.toLowerCase().includes(term)),
    );
  }
  get itemCount() { return this.cart.reduce((sum, item) => sum + item.quantity, 0); }
  get total() { return this.cart.reduce((sum, item) => sum + item.product.price_cents * item.quantity, 0); }
  formatPrice(value: number) { return `CLP ${this.money.format(value / 100)}`; }
  add(product: Product) {
    const existing = this.cart.find(item => item.product.id === product.id);
    existing ? existing.quantity++ : this.cart.push({ product, quantity: 1 });
    this.persistCart();
  }
  change(item: CartItem, amount: number) {
    item.quantity += amount;
    if (item.quantity < 1) this.cart = this.cart.filter(entry => entry !== item);
    this.persistCart();
  }
  private persistCart() { localStorage.setItem(`smach-angular-cart-${this.tableNumber || 'public'}`, JSON.stringify(this.cart)); }
  private restoreCart() {
    try { this.cart = JSON.parse(localStorage.getItem(`smach-angular-cart-${this.tableNumber || 'public'}`) || '[]'); } catch { this.cart = []; }
  }
  openCheckout() {
    this.formError = '';
    if (!this.tableNumber || !this.tableToken) {
      this.formError = 'Para confirmar, abre el menú escaneando el QR de una mesa.';
      return;
    }
    this.cartOpen = false;
    this.checkoutOpen = true;
  }
  async submitOrder() {
    this.formError = '';
    if (!this.customerName.trim()) { this.formError = 'Ingresa tu nombre para continuar.'; return; }
    if (this.paymentMethod === 'card' && !this.paymentToken.trim()) { this.formError = 'Ingresa el dato de prueba de la tarjeta.'; return; }
    try {
      const response = await fetch('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        customer_name: this.customerName, notes: this.notes, payment_method: this.paymentMethod,
        payment_token: this.paymentToken, table_number: this.tableNumber, table_token: this.tableToken,
        items: this.cart.map(item => ({ product_id: item.product.id, quantity: item.quantity })),
      })});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'No pudimos crear el pedido.');
      this.tracking = { id: data.order_id, estimated_minutes: data.estimated_minutes, access_token: data.access_token, status: data.status };
      this.cart = []; this.persistCart(); this.checkoutOpen = false;
      localStorage.setItem(`smach-angular-order-${this.tableNumber}`, JSON.stringify(this.tracking));
      this.startTracking();
    } catch (error: unknown) {
      this.formError = error instanceof Error ? error.message : 'No pudimos enviar el pedido.';
    }
  }

  private restoreTracking() {
    if (!this.tableNumber) return;
    try {
      const saved = JSON.parse(localStorage.getItem(`smach-angular-order-${this.tableNumber}`) || 'null');
      if (saved?.id && saved?.access_token && !['delivered', 'cancelled'].includes(saved.status)) {
        this.tracking = saved;
        this.startTracking();
      }
    } catch {
      localStorage.removeItem(`smach-angular-order-${this.tableNumber}`);
    }
  }

  private startTracking() {
    if (this.trackingTimer) clearInterval(this.trackingTimer);
    this.refreshTracking();
    this.trackingTimer = setInterval(() => this.refreshTracking(), 10000);
  }

  private async refreshTracking() {
    if (!this.tracking?.id || !this.tracking?.access_token) return;
    try {
      const response = await fetch(`/api/orders/${this.tracking.id}?access=${encodeURIComponent(this.tracking.access_token)}`);
      if (!response.ok) throw new Error('No se pudo actualizar el seguimiento');
      const data: OrderResponse = await response.json();
      this.tracking = { ...data.order, items: data.items, access_token: this.tracking.access_token };
      localStorage.setItem(`smach-angular-order-${this.tableNumber}`, JSON.stringify(this.tracking));
      if (['delivered', 'cancelled'].includes(this.tracking.status)) {
        if (this.trackingTimer) clearInterval(this.trackingTimer);
      }
    } catch {
      // El siguiente ciclo recuperará la conexión sin interrumpir el pedido visible.
    }
  }

  trackingMessage() {
    const messages: Record<string, string> = {
      pending: 'Recibimos tu pedido. El restaurante lo revisará pronto.',
      confirmed: 'Tu pedido fue confirmado y comenzará a prepararse.',
      preparing: 'Tu hamburguesa está en la parrilla.',
      ready: '¡Tu pedido está listo!',
      delivered: 'Gracias por elegir Smach & Grill.',
      cancelled: 'Este pedido fue cancelado.',
    };
    return messages[this.tracking?.status || ''] || 'Estamos actualizando tu pedido.';
  }

  trackingProgress() {
    const progress = { pending: 12, confirmed: 35, preparing: 65, ready: 100, delivered: 100, cancelled: 100 } as Record<string, number>;
    return progress[this.tracking?.status || ''] || 12;
  }
}
