const formatPrice = cents => `CLP ${new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 }).format(cents / 100)}`;
const grid = document.querySelector("#menu-grid");
const categories = document.querySelector("#categories");
const search = document.querySelector("#search");
const resultMessage = document.querySelector("#result-message");
const cartPanel = document.querySelector("#cart-panel");
const overlay = document.querySelector("#overlay");
const cartContent = document.querySelector("#cart-content");
const cartFooter = document.querySelector("#cart-footer");
const cartCount = document.querySelector("#cart-count");
const cartTotal = document.querySelector("#cart-total");
const toast = document.querySelector("#toast");
const dialog = document.querySelector("#checkout-dialog");
const form = document.querySelector("#checkout-form");
const formError = document.querySelector("#form-error");
let dishes = [];
let activeCategory = "Todos";
let cart = [];
let language = "es";
const translations = {
  es: { eyebrow: "Hamburguesas a la parrilla · Sabor sin vueltas", heroTitle: "Hamburguesas<br><span>que dejan huella.</span>", heroCopy: "Pan dorado, carne jugosa y combinaciones llenas de sabor. Elegí tu favorita y disfrutá.", viewMenu: "Ver el menú", chooseMoment: "Elegí tu momento", ourMenu: "Nuestro menú", search: "Buscar hamburguesa...", fresh: "Ingredientes frescos", freshSub: "Preparados todos los días", openToday: "Abierto hoy", options: "Opciones para todos", optionsSub: "Vegetarianas y sin TACC", footer: "Desarrollado por Jorge Paez, Patricio Chandia y Marco Mendez.", add: "+ Agregar", vegetarian: "Vegetariano", noResults: "No encontramos ese plato", tryAgain: "Probá con otro término o categoría.", total: "Total", checkout: "Confirmar pedido", checkoutNote: "Al confirmar, te contactaremos para coordinar el pago." },
  pt: { eyebrow: "Hambúrgueres na brasa · Sabor sem complicação", heroTitle: "Hambúrgueres<br><span>que marcam.</span>", heroCopy: "Pão dourado, carne suculenta e combinações cheias de sabor. Escolha o seu favorito.", viewMenu: "Ver o menu", chooseMoment: "Escolha seu momento", ourMenu: "Nosso menu", search: "Buscar hambúrguer...", fresh: "Ingredientes frescos", freshSub: "Preparados todos os dias", openToday: "Aberto hoje", options: "Opções para todos", optionsSub: "Vegetarianas e sem glúten", footer: "Desenvolvido por Jorge Paez, Patricio Chandia e Marco Mendez.", add: "+ Adicionar", vegetarian: "Vegetariano", noResults: "Não encontramos esse prato", tryAgain: "Tente outro termo ou categoria.", total: "Total", checkout: "Confirmar pedido", checkoutNote: "Ao confirmar, entraremos em contato para combinar o pagamento." },
  en: { eyebrow: "Grilled burgers · Straight-up flavor", heroTitle: "Burgers<br><span>that leave a mark.</span>", heroCopy: "Toasted buns, juicy patties and bold combinations. Pick your favorite and enjoy.", viewMenu: "View menu", chooseMoment: "Choose your moment", ourMenu: "Our menu", search: "Search burgers...", fresh: "Fresh ingredients", freshSub: "Prepared every day", openToday: "Open today", options: "Options for everyone", optionsSub: "Vegetarian and gluten-free", footer: "Developed by Jorge Paez, Patricio Chandia and Marco Mendez.", add: "+ Add", vegetarian: "Vegetarian", noResults: "We couldn't find that dish", tryAgain: "Try another term or category.", total: "Total", checkout: "Place order", checkoutNote: "After confirming, we will contact you to arrange payment." },
};
const dishTranslations = {
  pt: { 1: ["Pão de massa madre", "Manteiga de ervas, azeite e sal marinho."], 2: ["Burrata cremosa", "Tomates assados, pesto de manjericão e focaccia."], 3: ["Batatas bravas", "Batatas rústicas, aioli de limão e páprica."], 4: ["Frango na brasa", "Com batatas ao alecrim, salada fresca e molho do assado."], 5: ["Risoto da estação", "Cogumelos, abóbora assada, parmesão e tomilho."], 6: ["Peixe do dia", "Peixe fresco, purê de couve-flor e manteiga de alcaparras."], 7: ["Salada de burrata", "Folhas verdes, pêssego, nozes e vinagrete de mel."], 8: ["Tiramisù da casa", "Mascarpone, café, cacau e biscoitos artesanais."], 9: ["Flan de doce de leite", "Flan caseiro, creme e crocante de amêndoas."], 10: ["Limonada com hortelã", "Limão espremido, hortelã e um toque de gengibre."], 11: ["Vinho da casa", "Taça de 150 ml."], 12: ["Água com gás", "Garrafa de 500 ml."] },
  en: { 1: ["Sourdough bread", "Herb butter, olive oil and sea salt."], 2: ["Creamy burrata", "Roasted tomatoes, basil pesto and focaccia."], 3: ["Patatas bravas", "Rustic potatoes, lemon aioli and paprika."], 4: ["Grilled chicken", "Rosemary potatoes, fresh salad and roasting jus."], 5: ["Seasonal risotto", "Mushrooms, roasted squash, parmesan and thyme."], 6: ["Catch of the day", "Fresh fish, cauliflower purée and caper butter."], 7: ["Burrata salad", "Greens, peach, walnuts and honey vinaigrette."], 8: ["House tiramisu", "Mascarpone, coffee, cocoa and artisan biscuits."], 9: ["Dulce de leche flan", "Homemade flan, cream and almond crunch."], 10: ["Mint lemonade", "Fresh lemon, mint and a touch of ginger."], 11: ["House wine", "150 ml glass."], 12: ["Sparkling water", "500 ml bottle."] },
};
const localizedDish = (dish, field) => (dishTranslations[language]?.[dish.id]?.[field === "name" ? 0 : 1] || dish[field]);
const categoryTranslations = {
  es: { "Para empezar": "Para empezar", Principales: "Principales", Ensaladas: "Ensaladas", "Dulce final": "Dulce final", Bebidas: "Bebidas" },
  pt: { "Para empezar": "Para começar", Principales: "Pratos principais", Ensaladas: "Saladas", "Dulce final": "Sobremesas", Bebidas: "Bebidas" },
  en: { "Para empezar": "Starters", Principales: "Mains", Ensaladas: "Salads", "Dulce final": "Desserts", Bebidas: "Drinks" },
};

async function loadMenu() {
  try {
    const response = await fetch("/api/menu");
    if (!response.ok) throw new Error("No se pudo cargar el menú");
    const data = await response.json();
    dishes = data.products;
    window.menuCategories = data.categories;
    renderCategories(data.categories);
    renderDishes();
  } catch (error) {
    grid.innerHTML = `<div class="no-results"><h3>No se pudo cargar el menú</h3><p>Comprobá que el servidor esté iniciado e intentá de nuevo.</p></div>`;
  }

}

function renderCategories(categoryList) {
  categories.innerHTML = "";
  ["Todos", ...categoryList.map(category => category.name)].forEach(category => {
    const button = document.createElement("button");
    button.className = `category-button${category === activeCategory ? " active" : ""}`;
    button.textContent = category === "Todos" ? (language === "es" ? "Todos" : language === "pt" ? "Todos" : "All") : categoryTranslations[language][category];
    button.type = "button";
    button.dataset.category = category;
    button.setAttribute("aria-pressed", category === activeCategory);
    button.addEventListener("click", () => {
      activeCategory = category;
      document.querySelectorAll(".category-button").forEach(item => {
        const selected = item.dataset.category === category;
        item.classList.toggle("active", selected);
        item.setAttribute("aria-pressed", selected);
      });
      renderDishes();
    });
    categories.append(button);
  });
}

function applyLanguage(nextLanguage) {
  language = nextLanguage;
  const t = translations[language];
  document.documentElement.lang = language;
  document.querySelectorAll("[data-i18n]").forEach(element => { element.innerHTML = t[element.dataset.i18n]; });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.placeholder = t[element.dataset.i18nPlaceholder]; });
  document.querySelectorAll(".language-button").forEach(button => button.classList.toggle("active", button.dataset.language === language));
  renderCategories(window.menuCategories || []);
  renderDishes();
}

function renderDishes() {
  const query = search.value.trim().toLowerCase();
  const visibleDishes = dishes.filter(dish => {
    const matchesCategory = activeCategory === "Todos" || dish.category === activeCategory;
    return matchesCategory && `${dish.name} ${dish.description}`.toLowerCase().includes(query);
  });
  const t = translations[language];
  grid.innerHTML = visibleDishes.length ? visibleDishes.map(dish => `
    <article class="menu-card">
      <div class="dish-image" aria-hidden="true">${dish.emoji}</div>
      <div class="dish-details">
        <div class="dish-title-row"><h3 class="dish-title">${localizedDish(dish, "name")}</h3><span class="dish-price">${formatPrice(dish.price_cents)}</span></div>
        <p class="dish-description">${localizedDish(dish, "description")}</p>
        <div class="tags">${dish.vegetarian ? `<span class="tag">${t.vegetarian}</span>` : ""}</div>
        <button class="add-button" type="button" data-id="${dish.id}" aria-label="${t.add} ${localizedDish(dish, "name")}">${t.add}</button>
      </div>
    </article>
  `).join("") : `<div class="no-results"><h3>${t.noResults}</h3><p>${t.tryAgain}</p></div>`;
  resultMessage.textContent = query || activeCategory !== "Todos" ? `${visibleDishes.length} ${language === "en" ? "results" : language === "pt" ? "resultados" : "opciones encontradas"}` : "";
  grid.querySelectorAll(".add-button").forEach(button => button.addEventListener("click", () => addToCart(Number(button.dataset.id))));
}

function addToCart(id) {
  const existing = cart.find(item => item.product_id === id);
  if (existing) existing.quantity += 1;
  else cart.push({ product_id: id, quantity: 1 });
  updateCart();
  showToast("Agregado a tu pedido");
}

function updateCart() {
  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
  cartCount.textContent = totalItems;
  cartCount.hidden = totalItems === 0;
  if (!cart.length) {
    cartContent.innerHTML = `<div class="empty-cart"><span aria-hidden="true">🍽️</span><h3>Tu pedido está vacío</h3><p>Sumá algo rico para empezar.</p></div>`;
    cartFooter.hidden = true;
    return;
  }
  cartContent.innerHTML = cart.map(item => {
    const dish = dishes.find(entry => entry.id === item.product_id);
    return `<div class="cart-item"><span class="cart-item-emoji" aria-hidden="true">${dish.emoji}</span><div class="cart-item-info"><strong>${dish.name}</strong><span>${formatPrice(dish.price_cents * item.quantity)}</span></div><div class="quantity"><button type="button" data-action="decrease" data-id="${dish.id}" aria-label="Quitar una porción de ${dish.name}">−</button><span aria-label="${item.quantity} unidades">${item.quantity}</span><button type="button" data-action="increase" data-id="${dish.id}" aria-label="Agregar una porción de ${dish.name}">+</button></div></div>`;
  }).join("");
  cartTotal.textContent = formatPrice(cart.reduce((sum, item) => sum + dishes.find(dish => dish.id === item.product_id).price_cents * item.quantity, 0));
  cartFooter.hidden = false;
  cartContent.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", () => changeQuantity(Number(button.dataset.id), button.dataset.action)));
}

function changeQuantity(id, action) {
  const item = cart.find(entry => entry.product_id === id);
  if (!item) return;
  item.quantity += action === "increase" ? 1 : -1;
  cart = cart.filter(entry => entry.quantity > 0);
  updateCart();
}

function toggleCart(open) {
  cartPanel.classList.toggle("open", open);
  cartPanel.setAttribute("aria-hidden", String(!open));
  overlay.hidden = !open;
  document.body.style.overflow = open ? "hidden" : "";
  if (open) document.querySelector("#close-cart").focus();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

function openCheckout() {
  if (!cart.length) return;
  dialog.hidden = false;
  document.querySelector("#customer-name").focus();
}

async function submitOrder(event) {
  event.preventDefault();
  formError.textContent = "";
  const data = Object.fromEntries(new FormData(form));
  try {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...data, items: cart }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo guardar el pedido");
    cart = [];
    form.reset();
    updateCart();
    dialog.hidden = true;
    toggleCart(false);
    showToast(`Pedido #${result.order_id} recibido correctamente`);
  } catch (error) {
    formError.textContent = error.message;
  }
}

search.addEventListener("input", renderDishes);
document.querySelectorAll(".language-button").forEach(button => button.addEventListener("click", () => applyLanguage(button.dataset.language)));
document.querySelector("#open-cart").addEventListener("click", () => toggleCart(true));
document.querySelector("#close-cart").addEventListener("click", () => toggleCart(false));
overlay.addEventListener("click", () => toggleCart(false));
document.querySelector("#checkout").addEventListener("click", openCheckout);
document.querySelector("#close-dialog").addEventListener("click", () => { dialog.hidden = true; });
form.addEventListener("submit", submitOrder);
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    if (!dialog.hidden) dialog.hidden = true;
    else if (cartPanel.classList.contains("open")) toggleCart(false);
  }
});
updateCart();
loadMenu();
