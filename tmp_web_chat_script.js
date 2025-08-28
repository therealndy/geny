(function(){
  const urlParams = new URLSearchParams(window.location.search);
  const explicit = urlParams.get('backend');
  const defaultLocal = 'http://127.0.0.1:8017';

  async function chooseBackend() {
    if (explicit) return explicit.replace(/\/$/, '');
    try {
      if (location.protocol === 'http:' || location.protocol === 'https:') {
        const controller = new AbortController();
        const to = setTimeout(() => controller.abort(), 1500);
        try {
          const probeUrl = location.origin.replace(/\/$/, '') + '/healthz';
          const r = await fetch(probeUrl, { cache: 'no-store', signal: controller.signal });
          clearTimeout(to);
          const ct = (r.headers.get('content-type') || '').toLowerCase();
          if (r.ok && ct.includes('application/json')) return location.origin.replace(/\/$/, '');
        } catch (e) { clearTimeout(to); }
      }
    } catch (e) {}
    return defaultLocal;
  }

  // DOM refs
  let backendBase = defaultLocal;
  let backendUrl = backendBase + '/chat';
  const messagesDiv = document.getElementById('messages');
  const input = document.getElementById('msgInput');
  const sendBtn = document.getElementById('sendBtn');
  const tabContent = document.getElementById('tabContent');
  const tabButtons = Array.from(document.querySelectorAll('.tabbtn'));

  async function fetchAndRenderTab(tab) {
    if (tab === 'story') {
      const endpoint = backendBase.replace(/\/$/, '') + '/world/learning';
      try {
        const r = await fetch(endpoint);
        const text = await r.text();
        try { const j = JSON.parse(text); tabContent.innerText = (j && j.life_summary && j.life_summary.summary) ? j.life_summary.summary : 'No story yet.'; }
        catch (pe) { tabContent.innerText = 'Error loading tab: response not JSON (status=' + (r && r.status) + ')'; }
      } catch (err) { tabContent.innerText = 'Error loading tab: ' + err; }

    } else if (tab === 'age') {
      const endpoint = backendBase.replace(/\/$/, '') + '/world/virtual-age';
      try {
        const r = await fetch(endpoint);
        const text = await r.text();
        let j = null; try { j = JSON.parse(text); } catch (pe) { tabContent.innerText = 'Error loading age: API did not return JSON'; return; }
        if (j && j.age) {
          const a = j.age;
          tabContent.innerHTML = '<div>Virtual age: ' + a.years + 'y ' + a.days + 'd ' + a.hours + 'h ' + a.minutes + 'm (scale ' + a.scale + ')</div>' +
                                 '<div style="margin-top:8px;"><button id="saveAgeBtn" style="background:#2CB67D;color:#fff;border:none;border-radius:6px;padding:8px 12px;cursor:pointer">Save to diary</button>' +
                                 '<span id="saveResult" style="margin-left:10px;color:#ddd"></span></div>';
          const saveBtn = document.getElementById('saveAgeBtn');
          const saveResult = document.getElementById('saveResult');
          saveBtn.addEventListener('click', async () => {
            saveBtn.disabled = true; saveResult.textContent = 'Saving...';
            try { const r2 = await fetch(endpoint + '?persist=1'); const j2 = await r2.json(); saveResult.textContent = (j2 && j2.saved) ? ('Saved: ' + (j2.sentence || '')) : 'Not saved'; }
            catch (err) { saveResult.textContent = 'Error: ' + err; } finally { saveBtn.disabled = false; }
          });
        } else { tabContent.innerText = 'No age data available.'; }

    } else if (tab === 'status') {
      try { const r = await fetch(backendBase.replace(/\/$/, '') + '/world/learning'); const text = await r.text(); const j = JSON.parse(text); tabContent.innerText = 'Activity: ' + ((j && j.presence && j.presence.method) || 'internal') + ', Exploration running: ' + ((j && j.exploration && j.exploration.running) || ''); }
      catch (err) { tabContent.innerText = 'Error loading tab: ' + err; }

    } else if (tab === 'relation') {
      try { const r = await fetch(backendBase.replace(/\/$/, '') + '/world/learning'); const text = await r.text(); const j = JSON.parse(text); tabContent.innerText = (j && j.life_summary && j.life_summary.summary && j.life_summary.summary.split('\n')[0]) || 'No relations.'; }
      catch (err) { tabContent.innerText = 'Error loading tab: ' + err; }
    }
  }

  (async function init() {
    const b = await chooseBackend(); backendBase = b; backendUrl = backendBase.replace(/\/$/, '') + '/chat';
    tabButtons.forEach(btn => btn.addEventListener('click', () => { tabButtons.forEach(x => x.classList.remove('active')); btn.classList.add('active'); fetchAndRenderTab(btn.getAttribute('data-tab')); }));
    (tabButtons[0] || { click: () => {} }).click();
  })();

  function addMsg(text, who) { const div = document.createElement('div'); div.className = 'msg ' + who; if (who === 'geny') div.innerHTML = text; else div.textContent = text; messagesDiv.appendChild(div); messagesDiv.scrollTop = messagesDiv.scrollHeight; }

  sendBtn.onclick = async () => {
    const msg = input.value.trim(); if (!msg) return; addMsg(msg, 'user'); input.value = ''; sendBtn.disabled = true; const typingNode = document.createElement('div'); typingNode.className = 'msg geny'; typingNode.textContent = 'Geny is typing...'; messagesDiv.appendChild(typingNode); messagesDiv.scrollTop = messagesDiv.scrollHeight;
    try {
      const res = await fetch(backendUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: msg }) });
      if (!res.ok) { let bodyText = ''; try { bodyText = await res.text(); } catch (e) { bodyText = String(e); } typingNode.remove(); addMsg('[Server error: ' + res.status + '] ' + bodyText.slice(0,300), 'geny'); return; }
      let data = null; try { data = await res.json(); } catch (pe) { const text = await res.text(); typingNode.remove(); addMsg('[Invalid JSON response] ' + text.slice(0,300), 'geny'); return; }
      typingNode.remove(); const replyText = (data && (data.message || data.reply)) || '[No reply]'; addMsg(replyText, 'geny');
    } catch (e) { try { messagesDiv.lastChild.remove(); } catch (err) {} addMsg('[Error: ' + e + ']', 'geny'); } finally { sendBtn.disabled = false; input.focus(); }
  };

  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); } else if (e.key === 'Enter' && e.shiftKey) { const start = input.selectionStart; const end = input.selectionEnd; input.value = input.value.substring(0, start) + "\n" + input.value.substring(end); input.selectionStart = input.selectionEnd = start + 1; e.preventDefault(); } });

  window.__genyDebug = { getState() { try { return { backendBase, backendUrl, sendBtnOnclickType: typeof sendBtn.onclick }; } catch (e) { return { error: String(e) }; } }, sendTest(msg) { try { input.value = String(msg || 'test'); sendBtn.click(); return true; } catch (e) { return { error: String(e) }; } } };
})();
