(() => {
    document.querySelector('[data-menu-status-filter]')?.addEventListener('change', event => event.target.form.requestSubmit());
    const table = document.querySelector('[data-menu-move-url]');
    if (!table) return;
    const form = document.querySelector('[data-menu-move-form]');
    const status = document.querySelector('[data-menu-move-status]');
    if (!form || !status) return;
    const rows = [...table.querySelectorAll('tbody tr[data-menu-id]')];
    let source = null;
    let busy = false;
    const clearDrop = () => rows.forEach(row => delete row.dataset.drop);
    const positionAt = (event, row) => {
        const rect = row.getBoundingClientRect();
        const fraction = (event.clientY - rect.top) / (rect.height || 1);
        return fraction < 0.28 ? 'before' : fraction > 0.72 ? 'after' : 'inside';
    };
    const move = async (sourceId, targetId, position) => {
        if (busy) return;
        if (sourceId === targetId) { status.textContent = '서로 다른 메뉴를 선택하세요.'; return; }
        busy = true;
        form.querySelector('button').disabled = true;
        status.textContent = '메뉴 이동을 저장하고 있습니다…';
        try {
            const token = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
            const response = await fetch(table.dataset.menuMoveUrl, {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                body: JSON.stringify({ source: sourceId, target: targetId, position, revision: table.dataset.menuRevision })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || '메뉴 이동을 저장하지 못했습니다. 로그인과 권한을 확인하세요.');
            window.location.reload();
        } catch (error) {
            status.textContent = error.message || '연결 오류로 메뉴를 저장하지 못했습니다.';
        } finally {
            busy = false; form.querySelector('button').disabled = false;
        }
    };
    rows.forEach(row => {
        row.querySelector('.menu-drag-handle').addEventListener('dragstart', event => {
            if (busy) { event.preventDefault(); return; }
            source = Number(row.dataset.menuId);
            event.dataTransfer.setData('text/plain', String(source));
            event.dataTransfer.effectAllowed = 'move';
            row.classList.add('menu-dragging');
        });
        row.addEventListener('dragover', event => {
            if (source === null || source === Number(row.dataset.menuId) || busy) return;
            event.preventDefault(); clearDrop();
            event.dataTransfer.dropEffect = 'move';
            row.dataset.drop = positionAt(event, row);
        });
        row.addEventListener('drop', event => {
            event.preventDefault();
            const target = Number(row.dataset.menuId);
            const position = positionAt(event, row);
            const currentSource = source;
            clearDrop();
            if (currentSource !== null && currentSource !== target) move(currentSource, target, position);
        });
    });
    table.addEventListener('dragend', () => {
        source = null; clearDrop(); rows.forEach(row => row.classList.remove('menu-dragging'));
    });
    form.addEventListener('submit', event => {
        event.preventDefault();
        move(Number(form.elements.source.value), Number(form.elements.target.value), form.elements.position.value);
    });
})();

