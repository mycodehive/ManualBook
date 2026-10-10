(() => {
    'use strict';
    const sidebar = document.getElementById('app-sidebar');
    if (!sidebar) return;
    const groups = [...sidebar.querySelectorAll('details[data-menu-code]')];
    const key = `manualbook.sidebar.groups.v1.${sidebar.dataset.menuStateUser}`;
    let saved;
    try {
        saved = JSON.parse(localStorage.getItem(key));
    } catch (_) { /* Storage may be unavailable or contain invalid JSON. */ }
    if (saved && typeof saved.groups === 'object' && saved.groups !== null) {
        groups.forEach(group => {
            const open = saved.groups[group.dataset.menuCode];
            if (typeof open === 'boolean') group.open = open;
        });
        if (Number.isFinite(saved.scrollTop) && saved.scrollTop >= 0) {
            requestAnimationFrame(() => { sidebar.scrollTop = saved.scrollTop; });
        }
    }
    const persist = () => {
        const state = {
            groups: Object.fromEntries(groups.map(group => [group.dataset.menuCode, group.open])),
            scrollTop: sidebar.scrollTop,
        };
        try { localStorage.setItem(key, JSON.stringify(state)); } catch (_) { /* Keep navigation usable. */ }
    };
    groups.forEach(group => group.addEventListener('toggle', persist));
    // Capture before navigation, even if a native toggle event is still queued.
    sidebar.addEventListener('click', event => {
        if (event.target.closest('a[href]')) persist();
    }, true);
    window.addEventListener('pagehide', persist);
})();

