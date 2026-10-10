// Apply the saved theme before styles load, including login and popup pages.
(() => {
    'use strict';
    let theme = 'light';
    try { if (localStorage.getItem('manualbook.theme') === 'dark') theme = 'dark'; } catch (_) {}
    document.documentElement.dataset.theme = theme;
})();

