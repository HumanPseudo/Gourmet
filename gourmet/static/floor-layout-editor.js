const TABLE_BOX = 56;

function statusColor(status) {
  return {
    available: '#28a745',
    occupied: '#dc3545',
    reserved: '#007bff',
    cleaning: '#6c757d',
    out_of_service: '#6c757d',
  }[status] || '#6c757d';
}

document.addEventListener('alpine:init', () => {
  Alpine.data('floorEditor', () => ({
    layout: { id: '', width: 800, height: 600 },
    items: [],
    availableTables: [],
    saving: false,
    message: '',
    dragOffset: { x: TABLE_BOX / 2, y: TABLE_BOX / 2 },

    get csrf() { return document.querySelector('meta[name=csrf-token]')?.content || ''; },

    init() {
      this.layout = JSON.parse(document.getElementById('layout-config').textContent);
      this.items = JSON.parse(document.getElementById('layout-items').textContent);
      this.availableTables = JSON.parse(document.getElementById('available-tables').textContent);
    },

    boardStyle() {
      return 'position:relative;width:' + this.layout.width + 'px;height:' + this.layout.height + 'px;'
        + 'background:#f8f9fa repeating-linear-gradient(0deg,transparent,transparent 24px,#eee 25px),'
        + 'repeating-linear-gradient(90deg,transparent,transparent 24px,#eee 25px);'
        + 'border:2px dashed #ced4da;border-radius:8px;max-width:100%;overflow:auto;';
    },

    itemStyle(item) {
      const radius = item.shape === 'round' ? '50%' : '8px';
      return 'position:absolute;left:' + item.pos_x + 'px;top:' + item.pos_y + 'px;'
        + 'width:' + TABLE_BOX + 'px;height:' + TABLE_BOX + 'px;display:flex;flex-direction:column;'
        + 'align-items:center;justify-content:center;cursor:grab;border-radius:' + radius + ';'
        + 'transform:rotate(' + item.rotation + 'deg);color:#fff;font-weight:700;font-size:13px;'
        + 'user-select:none;box-shadow:0 1px 3px rgba(0,0,0,.3);background:' + statusColor(item.status) + ';';
    },

    startDrag(event, index) {
      event.dataTransfer.setData('text/plain', JSON.stringify({ type: 'existing', index: index }));
      this.dragOffset = { x: event.offsetX, y: event.offsetY };
    },

    startDragNew(event, table) {
      event.dataTransfer.setData('text/plain', JSON.stringify({ type: 'new', table: table }));
      this.dragOffset = { x: TABLE_BOX / 2, y: TABLE_BOX / 2 };
    },

    onDrop(event) {
      const raw = event.dataTransfer.getData('text/plain');
      if (!raw) return;
      const payload = JSON.parse(raw);
      const rect = event.currentTarget.getBoundingClientRect();
      let x = Math.round(event.clientX - rect.left - this.dragOffset.x);
      let y = Math.round(event.clientY - rect.top - this.dragOffset.y);
      x = Math.max(0, Math.min(x, this.layout.width - TABLE_BOX));
      y = Math.max(0, Math.min(y, this.layout.height - TABLE_BOX));

      if (payload.type === 'existing') {
        this.items[payload.index].pos_x = x;
        this.items[payload.index].pos_y = y;
      } else if (payload.type === 'new') {
        this.items.push({
          table_id: payload.table.id,
          code: payload.table.code,
          capacity: payload.table.capacity,
          status: payload.table.status,
          pos_x: x,
          pos_y: y,
          shape: 'square',
          rotation: 0,
        });
        this.availableTables = this.availableTables.filter((t) => t.id !== payload.table.id);
      }
    },

    rotateItem(index) {
      const item = this.items[index];
      item.rotation = (item.rotation + 90) % 360;
    },

    removeItem(index) {
      const removed = this.items.splice(index, 1)[0];
      this.availableTables.push({ id: removed.table_id, code: removed.code, capacity: removed.capacity, status: removed.status });
    },

    async save() {
      this.saving = true;
      this.message = '';
      try {
        const response = await fetch('/pos/floor/layouts/' + this.layout.id + '/positions/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrf,
          },
          body: JSON.stringify({ items: this.items }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Error al guardar');
        this.message = 'Guardado: ' + data.count + ' mesa(s) posicionada(s).';
      } catch (e) {
        this.message = 'Error: ' + e.message;
      } finally {
        this.saving = false;
        setTimeout(() => { this.message = ''; }, 4000);
      }
    },
  }));
});
