document.body.addEventListener('htmx:configRequest', function(e) {
    e.detail.headers['X-CSRFToken'] = document.querySelector('meta[name=csrf-token]')?.content;
});
