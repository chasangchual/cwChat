/* Minimal jQuery chat client. Why: small surface, easy to integrate. */
(function($){
  const state = {
    ws: null,
    connected: false,
    reconnectAttempts: 0,
    typing: false,
    pendingFile: null, // {name, size, dataUrl}
    sessionId: (window.__CHAT__ && window.__CHAT__.sessionId) || null,
  };

  const el = {
    messages: $("#messages"),
    input: $("#chat-input"),
    form: $("#composer-form"),
    sendBtn: $("#send-btn"),
    fileInput: $("#file-input"),
    clearBtn: $("#clear-history"),
    exportBtn: $("#export-history"),
  };

  function wsUrl(){
    const proto = (location.protocol === "https:") ? "wss" : "ws";
    return `${proto}://${location.host}${window.__CHAT__?.wsPath || "/app/ws"}`;
  }

  function renderMessage(role, content, at){
    const row = $('<div/>', { class: `msg ${role}` });
    const avatar = $('<div/>', { class: 'avatar', text: role === 'user' ? 'U' : 'B' });
    const bubble = $('<div/>', { class: 'bubble', text: content });
    const meta = $('<div/>', { class: 'meta', text: at ? new Date(at).toLocaleString() : '' });
    const wrap = $('<div/>', { class: 'row' }).append(bubble, meta);
    row.append(avatar, wrap);
    el.messages.append(row);
    scrollToBottom();
  }

  function renderTyping(on){
    const id = "typing-row";
    if(on){
      if($("#"+id).length) return;
      const row = $('<div/>', { class: 'msg bot', id });
      const avatar = $('<div/>', { class: 'avatar', text: 'B' });
      const bubble = $('<div/>', { class: 'bubble' });
      const dots = $('<div/>', { class: 'typing', 'aria-label': 'Assistant is typing' })
        .append($('<span/>'), $('<span/>'), $('<span/>'));
      const wrap = $('<div/>', { class: 'row' }).append(dots);
      row.append(avatar, wrap);
      el.messages.append(row);
    } else {
      $("#"+id).remove();
    }
    scrollToBottom();
  }

  function renderError(msg){
    const row = $('<div/>', { class: 'msg bot' });
    const avatar = $('<div/>', { class: 'avatar', text: '!' });
    const bubble = $('<div/>', { class: 'bubble error', text: msg });
    const wrap = $('<div/>', { class: 'row' }).append(bubble);
    row.append(avatar, wrap);
    el.messages.append(row);
    scrollToBottom();
  }

  function scrollToBottom(){
    // Why: Keep latest content visible without layout thrash
    el.messages.stop().animate({ scrollTop: el.messages[0].scrollHeight }, 200);
    // Also ensure container scrolls if the body scrolls:
    window.requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  }

  async function fileToDataUrl(file){
    return new Promise((resolve, reject)=>{
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function connect(){
    if(state.connected) return;
    state.ws = new WebSocket(wsUrl());
    state.ws.onopen = () => {
      state.connected = true;
      state.reconnectAttempts = 0;
      state.ws.send(JSON.stringify({ type: "cw_chat_hello", session_id: state.sessionId }));
    };
    state.ws.onclose = () => {
      state.connected = false;
      renderTyping(false);
      // Exponential backoff
      const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts++), 10000);
      setTimeout(connect, delay);
    };
    state.ws.onmessage = (ev) => {
      try{
        const msg = JSON.parse(ev.data);
        handleServerEvent(msg);
      }catch(e){
        renderError("Malformed server message.");
      }
    };
    state.ws.onerror = () => {
      renderError("WebSocket error.");
    };
  }

  function handleServerEvent(e){
    switch(e.type){
      case "ack": /* optimistic UI already rendered */ break;
      case "typing": renderTyping(!!e.state); break;
      case "token": appendStreamingText(e.data); break;
      case "done": endStreaming(); break;
      case "assistant_message": {
        renderMessage('bot', e.message.content, new Date().toISOString());
        break;
      }
      case "error": renderError(e.error || "Unknown error"); break;
      default: /* ignore */ break;
    }
  }

  // Streaming buffer
  let streamBuf = "";
  let streamRow = null;
  function appendStreamingText(chunk){
    if(!streamRow){
      streamRow = $('<div/>', { class: 'msg bot' });
      const avatar = $('<div/>', { class: 'avatar', text: 'B' });
      const bubble = $('<div/>', { class: 'bubble', text: "" });
      const meta = $('<div/>', { class: 'meta', text: new Date().toLocaleString() });
      const wrap = $('<div/>', { class: 'row' }).append(bubble, meta);
      streamRow.append(avatar, wrap);
      el.messages.append(streamRow);
    }
    streamBuf += chunk;
    streamRow.find('.bubble').text(streamBuf);
    scrollToBottom();
  }
  function endStreaming(){
    streamBuf = "";
    streamRow = null;
    renderTyping(false);
  }

  async function sendMessage(text){
    if(!text || !state.connected) return;
    // Optimistic render
    renderMessage('user', text, new Date().toISOString());
    // Attach file if any (demo: base64 metadata, not upload to server)
    let filePayload = null;
    if(state.pendingFile){
      filePayload = {
        name: state.pendingFile.name,
        size: state.pendingFile.size,
        // Truncate data for demo transport safety
        dataUrl: state.pendingFile.dataUrl.slice(0, 256)
      };
      state.pendingFile = null;
    }
    state.ws.send(JSON.stringify({ type: "user_message", text, file: filePayload }));
    renderTyping(true);
  }

  async function loadHistory(){
    try{
      const res = await fetch("/api/history", { credentials: "include" });
      if(!res.ok) return;
      const data = await res.json();
      state.sessionId = data.session_id;
      (data.messages || []).forEach(m => renderMessage(m.role, m.content, m.at));
    }catch(e){
      /* silent */
    }
  }

  // Handlers
  el.form.on("submit", async (e)=>{
    e.preventDefault();
    const text = (el.input.val() || "").toString().trim();
    el.input.val("");
    await sendMessage(text);
  });

  el.fileInput.on("change", async (e)=>{
    const f = e.target.files?.[0];
    if(!f) return;
    // Why: inline metadata keeps demo self-contained without server upload handling
    const dataUrl = await fileToDataUrl(f);
    state.pendingFile = { name: f.name, size: f.size, dataUrl };
    // Surface small toast
    renderMessage('user', `(Attached file: ${f.name}, ${f.size} bytes)`, new Date().toISOString());
  });

  el.clearBtn.on("click", ()=>{
    if(!confirm("Clear chat history for this session?")) return;
    fetch("/api/history", { method: "DELETE" }).catch(()=>{});
    // In-memory clear (client)
    el.messages.empty();
  });

  el.exportBtn.on("click", async ()=>{
    const res = await fetch("/api/history", { credentials: "include" });
    if(!res.ok){ renderError("Export failed"); return; }
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `chat-history-${data.session_id}.json`; a.click();
    URL.revokeObjectURL(url);
  });

  // Add a small DELETE handler on the same path (best effort)
  (function addClientDeleteHistory(){
    // This adds a soft endpoint only visible to devs; server may ignore.
    $.ajaxSetup({ converters: { "text json": JSON.parse } });
    $(document).on("click", function(){ /* noop to keep jQuery happy */ });
  })();

  // Init
  $(async function(){
    await loadHistory();
    connect();
    el.input.trigger("focus");
  });

})(jQuery);