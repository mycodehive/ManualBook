(() => {
    'use strict';
    const body = document.body;
    const storage = {
        get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} }
    };
    const sidebarToggle = document.querySelector('[data-sidebar-toggle]');
    const sidebar = document.getElementById('app-sidebar');
    const isMobile = () => window.matchMedia('(max-width: 900px)').matches;
    const syncSidebar = () => {
        const expanded = isMobile() ? body.classList.contains('mobile-menu-open') : !body.classList.contains('sidebar-collapsed');
        sidebarToggle?.setAttribute('aria-expanded', String(expanded));
        sidebar?.toggleAttribute('inert', !expanded);
    };
    const closeSidebar = () => { body.classList.remove('mobile-menu-open'); syncSidebar(); };
    if (storage.get('manualbook.sidebar.collapsed') === 'true') body.classList.add('sidebar-collapsed');
    sidebarToggle?.addEventListener('click', () => {
        if (isMobile()) body.classList.toggle('mobile-menu-open');
        else { body.classList.toggle('sidebar-collapsed'); storage.set('manualbook.sidebar.collapsed', String(body.classList.contains('sidebar-collapsed'))); }
        syncSidebar();
    });
    document.querySelectorAll('[data-mobile-menu-close], [data-mobile-menu-backdrop]').forEach(el => el.addEventListener('click', closeSidebar));
    window.addEventListener('resize', () => { if (!isMobile()) body.classList.remove('mobile-menu-open'); syncSidebar(); });
    syncSidebar();
    const themeButton = document.querySelector('[data-theme-toggle]');
    const applyTheme = (value) => {
        const theme = value === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.theme = theme;
        body.dataset.theme = theme;
        themeButton?.setAttribute('aria-pressed', String(theme === 'dark'));
        document.dispatchEvent(new CustomEvent('themechange', {detail: {theme}}));
    };
    applyTheme(storage.get('manualbook.theme') || 'light');
    themeButton?.addEventListener('click', () => { const theme = body.dataset.theme === 'dark' ? 'light' : 'dark'; applyTheme(theme); storage.set('manualbook.theme', theme); });
    const userTrigger = document.querySelector('[data-user-menu-trigger]');
    const userPanel = document.querySelector('[data-user-menu-panel]');
    const closeUserMenu = () => { if (userPanel) userPanel.hidden = true; userTrigger?.setAttribute('aria-expanded', 'false'); };
    userTrigger?.addEventListener('click', () => { if (!userPanel) return; userPanel.hidden = !userPanel.hidden; userTrigger.setAttribute('aria-expanded', String(!userPanel.hidden)); });
    document.addEventListener('click', event => { if (!event.target.closest('.user-menu')) closeUserMenu(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeUserMenu(); closeSidebar(); } });
    if (typeof window.flatpickr === 'function') {
        document.querySelectorAll('input[type="date"]:not([data-flatpickr-applied])').forEach(input => {
            input.dataset.flatpickrApplied = 'true'; input.classList.add('date-input-modern');
            const initialValue = input.value; input.type = 'text'; input.autocomplete = 'off';
            window.flatpickr(input, { allowInput: true, dateFormat: 'Y-m-d', defaultDate: initialValue || null, disableMobile: true, locale: window.flatpickr.l10ns?.ko || 'default', monthSelectorType: 'static' });
        });
    }
    const passwordToggle = document.querySelector('[data-password-toggle]');
    const passwordInput = document.getElementById('id_password');
    passwordToggle?.addEventListener('click', () => {
        if (!passwordInput) return;
        const visible = passwordInput.type === 'password';
        passwordInput.type = visible ? 'text' : 'password';
        passwordToggle.textContent = visible ? '숨김' : '보기';
        passwordToggle.setAttribute('aria-label', visible ? '비밀번호 숨기기' : '비밀번호 보기');
        passwordToggle.setAttribute('aria-pressed', String(visible));
    });
})();
