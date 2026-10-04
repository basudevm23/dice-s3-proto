/* common.js - shared helpers for every screen. All screens read ONE shared state from the server. */
const WN = {
  staticData: null,
  state: null,

  async getStatic() {
    if (!this.staticData) this.staticData = await (await fetch('/api/static')).json();
    return this.staticData;
  },

  /* Ask the server for the live state every `ms` milliseconds and call render(state). */
  poll(render, ms = 1000) {
    let busy = false;
    const tick = async () => {
      if (busy) return;
      busy = true;
      try {
        const r = await fetch('/api/state', { cache: 'no-store' });
        if (!r.ok) throw new Error(r.status);
        this.state = await r.json();
        render(this.state);
        WN.setConn(true);
      } catch (e) {
        WN.setConn(false);
      } finally {
        busy = false;
      }
    };
    tick();
    return setInterval(tick, ms);
  },

  post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(r => r.json());
  },
  control(action, value) { return this.post('/api/control', { action, value }); },

  setConn(ok) { document.querySelectorAll('.conn').forEach(el => el.classList.toggle('off', !ok)); },

  inr(v) { return v == null ? '–' : '₹' + Math.round(v).toLocaleString('en-IN'); },
  pct(v, d = 0) { return v == null ? '–' : (v * 100).toFixed(d) + '%'; },
  esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); },

  toast(text, ms = 2600) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms);
  },

  /* Control bar used on the hub and presenter pages. Built once, then kept in sync. */
  async mountControls(el) {
    const st = await this.getStatic();
    const opts = Object.entries(st.districts)
      .map(([k, v]) => `<option value="${k}">${WN.esc(v.name)} (${k}) · ${v.orders} orders</option>`).join('');
    el.innerHTML = `
      <select data-c="district" title="District (PIN first 3 digits)">${opts}</select>
      <button data-c="play" title="Play / pause the clock">⏸ Pause</button>
      <select data-c="speed" title="Speed of the clock">
        <option value="6">Fast (6 s = 1 day)</option>
        <option value="20">Normal (20 s = 1 day)</option>
        <option value="60">Slow (60 s = 1 day)</option>
      </select>
      <select data-c="shelf" title="Shelf size at the hub (demo setting). Make it small to show the rule choosing which parcels keep a slot.">
        <option value="10">Shelf: 10 slots</option>
        <option value="40">Shelf: 40 slots</option>
        <option value="100">Shelf: 100 slots</option>
      </select>
      <button data-c="next" title="Bring the next real refused parcel forward to now">Next refused parcel now</button>
      <label title="If nobody answers on the rider phone, answer automatically after the countdown">
        <input type="checkbox" data-c="auto"> Auto-rider</label>
      <button data-c="reset" title="Start the district again from day 1">Reset</button>
      <span class="conn" title="Live connection"></span>`;
    const q = s => el.querySelector(`[data-c="${s}"]`);
    q('district').onchange = e => WN.control('reset', e.target.value);
    q('play').onclick = () => WN.control(WN.state?.clock.playing ? 'pause' : 'play');
    q('speed').onchange = e => WN.control('speed', Number(e.target.value));
    q('shelf').onchange = e => WN.control('shelf', Number(e.target.value));
    q('next').onclick = () => WN.control('next_parcel').then(() => WN.toast('Next real refused parcel sent to the rider'));
    q('auto').onchange = e => WN.control('auto_rider', e.target.checked);
    q('reset').onclick = () => WN.control('reset', WN.state?.district);
    return s => {   // sync function: call with the latest state
      if (document.activeElement !== q('district')) q('district').value = s.district;
      if (document.activeElement !== q('speed')) q('speed').value = String(s.settings.seconds_per_day);
      if (document.activeElement !== q('shelf')) q('shelf').value = String(s.settings.shelf_slots);
      q('play').textContent = s.clock.playing ? '⏸ Pause' : (s.clock.ended ? '■ Ended' : '▶ Play');
      q('auto').checked = s.settings.auto_rider;
      q('next').disabled = s.clock.next_refusal_in_days == null;
    };
  },

  /* ---- language (English / Hindi) for the rider and hub apps ---- */
  lang: (() => { try { return localStorage.getItem('wn_lang') || 'en'; } catch (e) { return 'en'; } })(),
  setLang(l) { this.lang = l; try { localStorage.setItem('wn_lang', l); } catch (e) {} },
  t(en, hi) { return this.lang === 'hi' && hi ? hi : en; },
  langButton() {
    return `<button class="langbtn" data-lang title="English / हिंदी">${this.lang === 'hi' ? 'English' : 'हिंदी'}</button>`;
  },

  /* chance of a nearby buyer -> a word anyone understands */
  level(p) {
    if (p >= 0.3) return { key: 'high', en: 'High', hi: 'ज़्यादा' };
    if (p >= 0.1) return { key: 'med', en: 'Medium', hi: 'मध्यम' };
    return { key: 'low', en: 'Low', hi: 'कम' };
  },

  clockText(s) {
    return `Replaying ${s.clock.date} · day ${s.clock.day} of ${s.clock.days_total}`;
  },
};
