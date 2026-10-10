(() => {
  let color;
  try {color = JSON.parse(document.getElementById('platform-brand-color')?.textContent || 'null');} catch (_) {}
  if (!/^#[0-9a-f]{6}$/i.test(color || '')) return;
  const root = document.documentElement;
  const update = () => {
    root.style.setProperty('--action', color);
    root.style.setProperty('--action-hover', `color-mix(in srgb, ${color} 85%, black)`);
    if (root.dataset.theme === 'dark') root.style.removeProperty('--accent');
    else root.style.setProperty('--accent', color);
  };
  update(); document.addEventListener('themechange', update);
})();
