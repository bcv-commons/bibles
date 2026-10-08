import { renderChapter } from '../src/render.js';
import { loadPkf, pkfLanguage, optionsFromAppConfig } from '../src/sources/pkf.js';

const $ = (id) => document.getElementById(id);
const state = { pkf: null, doc: null, lang: null, configOptions: {} };

const status = (msg) => ($('status').textContent = msg);

// PKF: shared sheet + the language's delta.css, scoped by data-iso on #container.
// Other sources: the shared sheet alone, with example.css's default themes.
function setStyles(lang, iso) {
    const [shared, delta] = lang?.stylesheets || [];
    if (shared) $('sab-shared').href = shared;
    const d = $('sab-delta');
    if (delta) {
        d.href = delta;
        d.disabled = false;
        $('container').dataset.iso = iso;
    } else {
        d.disabled = true;
        delete $('container').dataset.iso;
    }
}

function options() {
    const o = { ...state.configOptions, notes: $('opt-notes').value, introduction: $('opt-intro').value };
    if ($('opt-chapter').value) o.chapterNumber = $('opt-chapter').value;
    if ($('opt-layout').value) o.verseLayout = $('opt-layout').value;
    return o;
}

function render() {
    if (!state.doc) return;
    const o = options();
    const r = renderChapter(state.doc, o);
    const content = $('content');
    content.innerHTML = r.html;
    content.dir = o.direction || 'ltr';
    $('introduction').innerHTML = r.introduction;
    $('warnings').textContent = r.warnings.length ? `Warnings: ${r.warnings.join(' · ')}` : '';
}

async function loadLanguage(iso) {
    status(`Loading ${iso}…`);
    state.lang = await pkfLanguage(iso);
    const { options: cfgOpts, warnings } = optionsFromAppConfig(state.lang.appConfig);
    state.configOptions = cfgOpts;
    if (warnings.length) console.warn(warnings);
    setStyles(state.lang, iso);
    const sel = $('collection');
    sel.innerHTML = state.lang.collections.map((c, i) => `<option value="${i}">${c.pkf.split('.')[0]}</option>`).join('');
    sel.hidden = state.lang.collections.length < 2;
    await loadCollection(0);
}

async function loadCollection(i) {
    const c = state.lang.collections[i];
    status(`Downloading ${c.pkf} (${Math.round((c.pkf_bytes || 0) / 1024)} KB)…`);
    const bytes = new Uint8Array(await (await fetch(c.url)).arrayBuffer());
    status('Decoding…');
    await new Promise((r) => setTimeout(r)); // let the status paint before the synchronous decode
    state.pkf = loadPkf(bytes);
    $('book').innerHTML = state.pkf.books.map((b) => `<option>${b}</option>`).join('');
    $('book').disabled = false;
    const want = new URLSearchParams(location.search).get('book');
    if (want && state.pkf.books.includes(want)) $('book').value = want;
    fillChapters();
}

function fillChapters() {
    const chs = state.pkf.chapters($('book').value);
    $('chapter').innerHTML = chs.map((c) => `<option>${c}</option>`).join('');
    $('chapter').disabled = false;
    const want = Number(new URLSearchParams(location.search).get('chapter'));
    if (chs.includes(want)) $('chapter').value = String(want);
    showChapter();
}

function showChapter() {
    const book = $('book').value;
    const ch = Number($('chapter').value);
    state.doc = state.pkf.sofria(book, ch);
    status(`${state.lang.name} · ${book} ${ch}`);
    render();
}

// notes: inline mode shows the hidden note div in a popup; collected mode uses the anchor links
document.addEventListener('click', (e) => {
    const caller = e.target.closest('[data-graft]');
    if (!caller) return;
    const body = caller.querySelector(`div[id="${CSS.escape(caller.dataset.graft)}"]`);
    if (!body) return;
    e.preventDefault();
    document.querySelector('.popup')?.remove();
    const pop = document.createElement('div');
    pop.className = 'popup';
    pop.innerHTML = `<button type="button">×</button>${body.innerHTML}`;
    pop.querySelector('button').onclick = () => pop.remove();
    document.body.appendChild(pop);
});

$('load').onclick = () => loadLanguage($('iso').value.trim()).catch((e) => status(e.message));
$('collection').onchange = (e) => loadCollection(Number(e.target.value)).catch((err) => status(err.message));
$('book').onchange = fillChapters;
$('chapter').onchange = showChapter;
for (const id of ['opt-notes', 'opt-chapter', 'opt-intro', 'opt-layout']) $(id).onchange = render;
$('file').onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    state.doc = JSON.parse(await f.text());
    state.configOptions = {};
    setStyles(null);
    status(f.name);
    render();
};

const params = new URLSearchParams(location.search);
if (params.get('sofria')) {
    // ?sofria=<url of a Sofria chapter JSON> (DBT text_json path, our own CDN files, …)
    fetch(params.get('sofria'))
        .then((r) => r.json())
        .then((d) => {
            state.doc = d;
            setStyles(null);
            status(params.get('sofria'));
            render();
        })
        .catch((e) => status(e.message));
} else {
    $('iso').value = params.get('iso') || 'aai';
    loadLanguage($('iso').value).catch((e) => status(e.message));
}
