document.addEventListener('alpine:init', () => {
  Alpine.data('posApp', () => ({
    categories: [], products: [], activeCat: '', search: '',
    cart: [], tableId: '', orderId: null,
    payMethod: 'cash', payAmount: 0, payError: '',
    totalPaid: 0, orderSubtotal: 0, orderTotal: 0,
    createOrderError: '', closeError: '', closed: false, tipAmount: 0,
    loadError: '',
    methods: [
      { value: 'cash', label: '\u{1F4B5} Efectivo', color: '#28a745' },
      { value: 'card', label: '\u{1F4B3} Tarjeta', color: '#007bff' },
      { value: 'transfer', label: '\u{1F3E6} Transf.', color: '#6f42c1' },
    ],
    taxLabels: { INC_8: 'INC 8%', IVA_19: 'IVA 19%', IVA_5: 'IVA 5%', EXENTO: 'Exento' },
    taxRates: { INC_8: 0.08, IVA_19: 0.19, IVA_5: 0.05, EXENTO: 0.0 },

    get csrf() { return document.querySelector('meta[name=csrf-token]')?.content || ''; },

    async init() {
      try {
        const [cats, prods] = await Promise.all([
          fetch('/api/menu/categories').then(r => { if (!r.ok) throw new Error('categories: ' + r.status); return r.json(); }),
          fetch('/api/menu/products').then(r => { if (!r.ok) throw new Error('products: ' + r.status); return r.json(); }),
        ]);
        this.categories = cats.items || cats || [];
        this.products = (prods.items || prods || []).filter(p => p.is_available);
      } catch (e) {
        this.loadError = 'Error al cargar datos: ' + e.message;
      }
    },

    get filteredProducts() {
      let p = this.products;
      if (this.search) {
        const q = this.search.toLowerCase();
        p = p.filter(x => x.name.toLowerCase().includes(q));
      }
      if (this.activeCat) p = p.filter(x => x.category_id === this.activeCat);
      return p;
    },

    _lineTotal(item) { return item.price * item.qty; },

    get subtotal() {
      return this.cart.reduce((s, i) => s + this._lineTotal(i), 0);
    },

    get taxBreakdown() {
      const map = {};
      for (const item of this.cart) {
        const label = this.taxLabels[item.tax_type] || item.tax_type;
        const rate = this.taxRates[item.tax_type] || 0;
        const tax = this._lineTotal(item) * rate;
        map[label] = (map[label] || 0) + tax;
      }
      return map;
    },

    get total() {
      let t = this.subtotal;
      for (const item of this.cart) {
        t += this._lineTotal(item) * (this.taxRates[item.tax_type] || 0);
      }
      return t;
    },

    get remaining() {
      const t = this.cart.length > 0 ? this.total : this.orderTotal;
      return Math.max(0, t - this.totalPaid);
    },

    addItem(p) {
      const existing = this.cart.find(i => i.id === p.id);
      if (existing) { existing.qty++; return; }
      this.cart.push({ id: p.id, name: p.name, price: parseFloat(p.price), tax_type: p.tax_type, qty: 1 });
    },

    changeQty(idx, delta) {
      const item = this.cart[idx];
      if (!item) return;
      item.qty = Math.max(1, item.qty + delta);
    },

    removeItem(idx) { this.cart.splice(idx, 1); },

    async createOrder() {
      this.createOrderError = '';
      if (this.cart.length === 0) return;
      const res = await fetch('/pos/create/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({
          table_id: this.tableId || null,
          items: this.cart.map(i => ({ product_id: i.id, quantity: i.qty })),
        }),
      });
      if (!res.ok) { const err = await res.json(); this.createOrderError = err.error || 'Error del servidor'; return; }
      const data = await res.json();
      this.orderId = data.id;
      this.orderSubtotal = parseFloat(data.subtotal || 0);
      this.orderTotal = parseFloat(data.total || 0);
      this.cart = [];
      this.totalPaid = parseFloat(data.total_paid || 0);
    },

    async addItems() {
      if (this.cart.length === 0) return;
      const res = await fetch('/pos/add-items/' + this.orderId + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({
          items: this.cart.map(i => ({ product_id: i.id, quantity: i.qty })),
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      this.orderSubtotal = parseFloat(data.subtotal || 0);
      this.orderTotal = parseFloat(data.total || 0);
      this.cart = [];
      this.totalPaid = parseFloat(data.total_paid || 0);
    },

    async pay() {
      this.payError = '';
      const res = await fetch('/pos/pay/' + this.orderId + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({ method: this.payMethod, amount: parseFloat(this.payAmount), tip: parseFloat(this.tipAmount || 0) }),
      });
      if (!res.ok) { const err = await res.json(); this.payError = err.error || 'Error'; return; }
      const data = await res.json();
      this.totalPaid += parseFloat(data.amount);
      this.payAmount = 0; this.tipAmount = 0; this.payError = '';
    },

    async closeOrder() {
      this.closeError = '';
      const res = await fetch('/pos/close/' + this.orderId + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': this.csrf },
      });
      if (!res.ok) { const err = await res.json(); this.closeError = err.error || 'Error'; return; }
      this.closed = true;
    },

    resetAll() {
      this.cart = []; this.orderId = null; this.payMethod = 'cash';
      this.payAmount = 0; this.payError = ''; this.totalPaid = 0;
      this.orderSubtotal = 0; this.orderTotal = 0;
      this.createOrderError = ''; this.closeError = ''; this.closed = false; this.tipAmount = 0;
    },
  }));
});
