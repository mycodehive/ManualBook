// Login in another tab can rotate the CSRF cookie after this form was rendered.
// Read only the current same-origin cookie; the server still validates every POST.
(() => {
    document.addEventListener('submit', event => {
        const form = event.target;
        if (!form.matches?.('[data-logout-form]')) return;
        const input = form.querySelector('input[name="csrfmiddlewaretoken"]');
        const cookie = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith('csrftoken='));
        if (!input || !cookie) return;
        const token = cookie.slice('csrftoken='.length);
        if (/^[a-zA-Z0-9]{32}$/.test(token)) input.value = token;
    });
})();
