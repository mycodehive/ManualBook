import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { TableKit } from '@tiptap/extension-table';
import Image from '@tiptap/extension-image';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import TurndownService from 'turndown';
import { gfm } from 'turndown-plugin-gfm';

const converter = new TurndownService({headingStyle: 'atx', codeBlockStyle: 'fenced', bulletListMarker: '-'});
converter.use(gfm);
converter.addRule('tasks', {
  filter: node => node.nodeName === 'LI' && node.dataset.type === 'taskItem',
  replacement: (_, node) => `\n- [${node.dataset.checked === 'true' ? 'x' : ' '}] ${converter.turndown(node.querySelector('div')?.innerHTML || node.textContent)}\n`,
});

document.querySelectorAll('textarea[data-block-editor]').forEach(textarea => {
  const holder = document.createElement('section');
  holder.className = 'block-editor';
  holder.setAttribute('aria-label', '문서 블록 편집기');
  const toolbar = document.createElement('div');
  toolbar.className = 'editor-toolbar';
  toolbar.setAttribute('role', 'toolbar');
  toolbar.setAttribute('aria-label', '문서 서식');
  const canvas = document.createElement('div');
  const status = document.createElement('p');
  status.className = 'muted';
  status.textContent = '블록 편집 · Markdown으로 저장됩니다. 복잡한 표의 셀 병합은 유지되지 않습니다.';
  holder.append(toolbar, canvas, status);
  textarea.before(holder);
  let initial = '<p></p>';
  try {initial = JSON.parse(document.getElementById('editor-initial-html')?.textContent || '"<p></p>"');} catch (_) {}
  let visualMode = true;
  const editor = new Editor({
    element: canvas,
    extensions: [StarterKit.configure({heading: {levels: [1,2,3,4,5,6]}, link: {openOnClick: false}}), TableKit.configure({table: {resizable: false}}), Image.configure({allowBase64: false}), TaskList, TaskItem.configure({nested: true})],
    content: initial,
    editorProps: {attributes: {'aria-label': '문서 본문', 'role': 'textbox', 'aria-multiline': 'true'}},
    onUpdate: ({editor}) => {
      if (!visualMode) return;
      textarea.value = converter.turndown(editor.getHTML());
      textarea.dispatchEvent(new Event('input', {bubbles: true}));
    },
  });
  const addButton = (label, command, title = label) => {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = label; button.title = title;
    button.className = 'button-secondary';
    button.addEventListener('click', command); toolbar.append(button); return button;
  };
  addButton('본문', () => editor.chain().focus().setParagraph().run());
  [1,2,3,4,5,6].forEach(level => addButton(`H${level}`, () => editor.chain().focus().toggleHeading({level}).run()));
  addButton('굵게', () => editor.chain().focus().toggleBold().run());
  addButton('기울임', () => editor.chain().focus().toggleItalic().run());
  addButton('취소선', () => editor.chain().focus().toggleStrike().run());
  addButton('목록', () => editor.chain().focus().toggleBulletList().run());
  addButton('번호', () => editor.chain().focus().toggleOrderedList().run());
  addButton('체크', () => editor.chain().focus().toggleTaskList().run());
  addButton('인용', () => editor.chain().focus().toggleBlockquote().run());
  addButton('코드', () => editor.chain().focus().toggleCodeBlock().run());
  addButton('표', () => editor.chain().focus().insertTable({rows: 3, cols: 3, withHeaderRow: true}).run());
  addButton('행 추가', () => editor.chain().focus().addRowAfter().run());
  addButton('열 추가', () => editor.chain().focus().addColumnAfter().run());
  addButton('표 삭제', () => editor.chain().focus().deleteTable().run());
  addButton('링크', () => {
    const url = window.prompt('내부 문서 경로 또는 https:// 링크', editor.getAttributes('link').href || '');
    if (url === null) return;
    if (!url) {editor.chain().focus().unsetLink().run(); return;}
    if (!(url.startsWith('/') && !url.startsWith('//')) && !/^https?:\/\//i.test(url)) {status.textContent = '내부 경로 또는 http(s) 주소를 입력하세요.'; return;}
    editor.chain().focus().extendMarkRange('link').setLink({href: url}).run();
  });
  addButton('이미지', () => {
    const url = window.prompt('권한 확인 첨부파일 이미지 주소 (/manuals/...)');
    if (url?.startsWith('/manuals/') && !url.includes('\\')) editor.chain().focus().setImage({src: url}).run();
    else if (url) status.textContent = '매뉴얼 첨부파일의 내부 주소를 입력하세요.';
  });
  addButton('실행 취소', () => editor.chain().focus().undo().run());
  addButton('다시 실행', () => editor.chain().focus().redo().run());
  const switcher = addButton('Markdown 편집', () => {
    if (!visualMode) {status.textContent = 'Markdown 변경을 저장한 뒤 블록 편집기로 다시 열어 주세요.'; return;}
    visualMode = false; canvas.hidden = true; textarea.hidden = false; textarea.focus();
    [...toolbar.children].forEach(button => {if (button !== switcher) button.disabled = true;});
    switcher.textContent = 'Markdown 모드';
  });
  textarea.hidden = true;
  textarea.form?.addEventListener('submit', () => {
    if (visualMode) textarea.value = converter.turndown(editor.getHTML());
  });
  // The Markdown field remains the progressive-enhancement fallback and autosave source.
  window.dispatchEvent(new CustomEvent('manualbook:editor-ready', {detail: {textarea, editor}}));
});
