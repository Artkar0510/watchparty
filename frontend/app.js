// === Кино вместе SPA ===
// Vanilla JS, hash-based routing, talks to nginx-proxied API on same origin.

// Fallback для фильмов без video_url. Берём локальный MP4 из nginx volume
// (frontend/videos/sample.mp4), чтобы плеер всегда что-то играл, не дёргая
// внешний CDN.
const DEMO_VIDEO = "/videos/sample.mp4";

// Распознаём YouTube-ссылки (watch?v=ID, youtu.be/ID, embed/ID).
// Для YouTube тег <video> не работает — нужен <iframe> embed.
function parseYouTubeId(url) {
  if (!url) return null;
  const patterns = [
    /[?&]v=([a-zA-Z0-9_-]{11})/,         // youtube.com/watch?v=ID
    /youtu\.be\/([a-zA-Z0-9_-]{11})/,    // youtu.be/ID
    /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/, // youtube.com/embed/ID
  ];
  for (const re of patterns) {
    const m = url.match(re);
    if (m) return m[1];
  }
  return null;
}

// Лениво грузим YouTube IFrame API один раз на всё приложение, отдаём Promise
// с глобальным YT. Без него new YT.Player(...) не существует.
// https://developers.google.com/youtube/iframe_api_reference
let _ytApiPromise = null;
function loadYouTubeApi() {
  if (_ytApiPromise) return _ytApiPromise;
  _ytApiPromise = new Promise((resolve) => {
    if (window.YT && window.YT.Player) return resolve(window.YT);
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      if (prev) try { prev(); } catch {}
      resolve(window.YT);
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  });
  return _ytApiPromise;
}
const DEMO_FILMS = [
  { title: "Big Buck Bunny",      description: "Открытый короткометражный мультфильм Blender Foundation.", rating: 7.8, type: "movie" },
  { title: "Sintel",              description: "Эпический короткий фильм Blender Foundation.",            rating: 8.1, type: "movie" },
  { title: "Tears of Steel",      description: "Фантастика от Mango Open Movie Project.",                 rating: 7.2, type: "movie" },
  { title: "Elephant's Dream",    description: "Первый открытый фильм Blender Institute.",                rating: 6.9, type: "movie" },
  { title: "Spring",              description: "Анимационный короткометражный фильм Blender.",            rating: 8.4, type: "movie" },
];

// ----------------- State & utils -----------------
const state = {
  token: localStorage.getItem("token") || null,
  refresh_token: localStorage.getItem("refresh_token") || null,
  me: null,
  ws: null,
  applyingRemote: false,
  pollTimer: null,
  notifTimer: null,
  unread: 0,
  usernameCache: {},
};

function $(sel) { return document.querySelector(sel); }
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return e;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function shortId(id) { return id ? id.slice(0, 8) : ""; }
function avatarColor(id) {
  const hue = id ? Array.from(id).reduce((a, c) => a + c.charCodeAt(0), 0) % 360 : 200;
  return `hsl(${hue} 65% 55%)`;
}

function toast(msg, kind = "") {
  const t = el("div", { class: "t " + kind }, msg);
  $("#toast").appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// ----------------- API client -----------------
async function api(path, { method = "GET", body, auth = true, retry = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers["Authorization"] = "Bearer " + state.token;
  const resp = await fetch(path, {
    method, headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 401 && auth && retry && state.refresh_token) {
    const ok = await tryRefresh();
    if (ok) return api(path, { method, body, auth, retry: false });
  }
  if (resp.status === 204) return null;
  let data = null;
  try { data = await resp.json(); } catch { data = null; }
  if (!resp.ok) {
    const detail = (data && data.detail) || resp.statusText;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = resp.status;
    throw err;
  }
  return data;
}

async function tryRefresh() {
  try {
    const r = await api("/api/v1/auth/refresh", {
      method: "POST",
      auth: false,
      body: { refresh_token: state.refresh_token },
    });
    state.token = r.access_token;
    state.refresh_token = r.refresh_token;
    localStorage.setItem("token", r.access_token);
    localStorage.setItem("refresh_token", r.refresh_token);
    return true;
  } catch {
    logout(false);
    return false;
  }
}

function logout(navigate = true) {
  state.token = state.refresh_token = state.me = null;
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  if (state.ws) try { state.ws.close(); } catch {}
  state.ws = null;
  if (navigate) location.hash = "#login";
  else render();
}

async function fetchUsername(userId) {
  if (!userId) return "?";
  if (state.usernameCache[userId]) return state.usernameCache[userId];
  try {
    const u = await api(`/api/v1/users/${userId}`);
    state.usernameCache[userId] = u.username;
    return u.username;
  } catch {
    return shortId(userId);
  }
}

// ----------------- Router -----------------
window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", boot);

async function boot() {
  if (state.token) {
    try { state.me = await api("/api/v1/users/me"); }
    catch { logout(false); }
  }
  if (!location.hash) location.hash = state.me ? "#catalog" : "#login";
  render();
  if (state.me) startNotifPolling();
}

function render() {
  const root = $("#app");
  clear(root);
  if (!state.me) {
    if (location.hash !== "#login") location.hash = "#login";
    root.append(viewLogin());
    return;
  }
  const route = location.hash.replace(/^#/, "");
  if (route.startsWith("watch/")) {
    root.append(viewWatch(route.split("/")[1]));
    return;
  }
  root.append(layout(route));
}

function layout(route) {
  const tab = (href, label, key) => el("a", {
    href: "#" + key,
    class: route === key ? "active" : "",
  }, label);
  const badge = state.unread > 0 ? el("span", { class: "notif-badge" }, state.unread) : null;

  const nav = el("div", { class: "topnav" },
    el("div", { class: "brand" }, "🎬 Кино вместе"),
    el("nav", { class: "tabs" },
      tab("#catalog", "Каталог", "catalog"),
      tab("#watchlist", "Хочу посмотреть", "watchlist"),
      tab("#friends", "Друзья", "friends"),
      tab("#matches", "Совпадения", "matches"),
      tab("#notifications", el("span", {}, "Уведомления", badge), "notifications"),
    ),
    el("span", { class: "me" }, state.me.username),
    el("button", { class: "ghost", onclick: () => logout() }, "Выйти"),
  );

  const main = el("main");
  if (route === "catalog") main.append(viewCatalog());
  else if (route === "watchlist") main.append(viewWatchlist());
  else if (route === "friends") main.append(viewFriends());
  else if (route === "matches") main.append(viewMatches());
  else if (route === "notifications") main.append(viewNotifications());
  else main.append(viewCatalog());

  return el("div", { class: "shell" }, nav, main);
}

// ----------------- Login -----------------
function viewLogin() {
  let mode = "login";
  const card = el("div", { class: "card" });
  const tabs = el("div", { class: "tabs-row" });
  const form = el("div");
  const errBox = el("div", { class: "error" });

  function renderForm() {
    clear(form);
    if (mode === "login") {
      const email = el("input", { type: "email", placeholder: "you@example.com" });
      const password = el("input", { type: "password", placeholder: "••••••••" });
      form.append(
        el("div", { class: "form-row" }, el("label", {}, "Email"), email),
        el("div", { class: "form-row" }, el("label", {}, "Пароль"), password),
        el("button", { onclick: async () => {
          errBox.textContent = "";
          try {
            const r = await api("/api/v1/auth/login", {
              method: "POST", auth: false,
              body: { email: email.value, password: password.value },
            });
            state.token = r.access_token;
            state.refresh_token = r.refresh_token;
            localStorage.setItem("token", r.access_token);
            localStorage.setItem("refresh_token", r.refresh_token);
            state.me = await api("/api/v1/users/me");
            location.hash = "#catalog";
            render();
            startNotifPolling();
          } catch (e) { errBox.textContent = e.message || "Ошибка"; }
        }}, "Войти"),
      );
    } else {
      const username = el("input", { placeholder: "alice" });
      const email = el("input", { type: "email", placeholder: "alice@example.com" });
      const password = el("input", { type: "password", placeholder: "минимум 8 символов" });
      form.append(
        el("div", { class: "form-row" }, el("label", {}, "Имя пользователя"), username),
        el("div", { class: "form-row" }, el("label", {}, "Email"), email),
        el("div", { class: "form-row" }, el("label", {}, "Пароль"), password),
        el("button", { onclick: async () => {
          errBox.textContent = "";
          try {
            await api("/api/v1/auth/register", {
              method: "POST", auth: false,
              body: { username: username.value, email: email.value, password: password.value },
            });
            const r = await api("/api/v1/auth/login", {
              method: "POST", auth: false,
              body: { email: email.value, password: password.value },
            });
            state.token = r.access_token;
            state.refresh_token = r.refresh_token;
            localStorage.setItem("token", r.access_token);
            localStorage.setItem("refresh_token", r.refresh_token);
            state.me = await api("/api/v1/users/me");
            location.hash = "#catalog";
            render();
            startNotifPolling();
          } catch (e) { errBox.textContent = e.message || "Ошибка"; }
        }}, "Зарегистрироваться"),
      );
    }
  }

  tabs.append(
    el("a", { class: mode === "login" ? "active" : "", onclick: () => { mode = "login"; tabs.children[0].className = "active"; tabs.children[1].className = ""; renderForm(); } }, "Вход"),
    el("a", { class: mode === "register" ? "active" : "", onclick: () => { mode = "register"; tabs.children[0].className = ""; tabs.children[1].className = "active"; renderForm(); } }, "Регистрация"),
  );

  card.append(
    el("h1", {}, "Кино вместе"),
    el("p", { class: "sub" }, "Совместный просмотр фильмов с друзьями"),
    tabs, form, errBox,
  );
  renderForm();
  return el("div", { class: "center" }, card);
}

// ----------------- Catalog -----------------
async function viewCatalog() {}
function viewCatalog() {
  const wrapper = el("div");
  const grid = el("div", { class: "films" }, el("div", { class: "empty" }, "Загрузка..."));
  const search = el("input", { placeholder: "Поиск по названию...", oninput: debounce(refresh, 300) });
  const seedBtn = el("button", { class: "ghost", onclick: async () => {
    seedBtn.disabled = true;
    try {
      for (const f of DEMO_FILMS) {
        try { await api("/api/v1/films", { method: "POST", body: { ...f, genre_ids: [] } }); }
        catch { /* dup ok */ }
      }
      toast("Демо-фильмы добавлены", "ok");
      await refresh();
    } finally { seedBtn.disabled = false; }
  }}, "+ Добавить демо-фильмы");

  wrapper.append(
    el("div", { class: "toolbar" },
      el("h2", {}, "Каталог"),
      search,
      seedBtn,
    ),
    grid,
  );

  async function refresh() {
    try {
      let films;
      if (search.value.trim().length >= 2) {
        films = await api(`/api/v1/films/search?query=${encodeURIComponent(search.value.trim())}`);
      } else {
        films = await api("/api/v1/films?page=1&page_size=50");
      }
      clear(grid);
      if (!films.length) { grid.append(el("div", { class: "empty" }, "Каталог пуст. Нажми «Добавить демо-фильмы».")); return; }
      for (const f of films) grid.append(filmCard(f, "catalog"));
    } catch (e) { toast("Ошибка загрузки: " + e.message, "error"); }
  }
  refresh();
  return wrapper;
}

function filmCard(f, ctx) {
  const card = el("div", { class: "film" },
    el("div", { class: "title" }, f.title),
    el("div", { class: "meta" }, `★ ${f.rating ?? "—"} · ${f.type === "movie" ? "Фильм" : "Сериал"}`),
    el("div", { class: "desc" }, f.description || ""),
  );
  const actions = el("div", { class: "actions" });
  if (ctx === "catalog") {
    actions.append(el("button", { class: "ghost", onclick: async (e) => {
      e.target.disabled = true;
      try { await api("/api/v1/watchlist", { method: "POST", body: { film_work_id: f.id } }); toast("Добавлено в список", "ok"); }
      catch (err) { toast(err.message, "error"); e.target.disabled = false; }
    }}, "+ Хочу посмотреть"));
  }
  actions.append(el("button", { onclick: async () => {
    try {
      const s = await api("/api/v1/sessions", { method: "POST", body: { film_id: f.id, invited_user_ids: [] } });
      location.hash = "#watch/" + s.session_id;
    } catch (e) { toast(e.message, "error"); }
  }}, "▶ Смотреть"));
  card.append(actions);
  return card;
}

// ----------------- Watchlist -----------------
function viewWatchlist() {
  const wrapper = el("div");
  const grid = el("div", { class: "films" }, el("div", { class: "empty" }, "Загрузка..."));
  wrapper.append(el("div", { class: "toolbar" }, el("h2", {}, "Хочу посмотреть")), grid);
  (async () => {
    try {
      const films = await api("/api/v1/watchlist");
      clear(grid);
      if (!films.length) { grid.append(el("div", { class: "empty" }, "Список пуст. Добавь фильмы из каталога.")); return; }
      for (const f of films) {
        const card = filmCard(f, "watchlist");
        card.querySelector(".actions").append(el("button", { class: "ghost danger", onclick: async (e) => {
          e.target.disabled = true;
          try { await api(`/api/v1/watchlist/${f.id}`, { method: "DELETE" }); card.remove(); toast("Удалено", "ok"); }
          catch (err) { toast(err.message, "error"); e.target.disabled = false; }
        }}, "Удалить"));
        grid.append(card);
      }
    } catch (e) { toast(e.message, "error"); }
  })();
  return wrapper;
}

// ----------------- Friends -----------------
function viewFriends() {
  const wrapper = el("div");
  const meBox = el("div", { class: "card" },
    el("h1", {}, "Поделись своим именем"),
    el("p", { class: "sub" }, `Чтобы кто-то добавил тебя в друзья, скажи ему свой ник: `, el("code", {}, state.me.username)),
  );
  const search = el("input", { placeholder: "Найти пользователя по имени (минимум 2 символа)..." });
  const searchResults = el("div");
  search.addEventListener("input", debounce(async () => {
    const q = search.value.trim();
    clear(searchResults);
    if (q.length < 2) return;
    try {
      const users = await api(`/api/v1/users/search?q=${encodeURIComponent(q)}`);
      if (!users.length) { searchResults.append(el("div", { class: "empty" }, "Никого не найдено")); return; }
      for (const u of users) {
        searchResults.append(el("div", { class: "user-row" },
          el("div", {},
            el("div", { class: "name" }, u.username),
            el("div", { class: "id" }, u.email),
          ),
          el("button", { onclick: async (e) => {
            e.target.disabled = true;
            try { await api("/api/v1/users/friends/request", { method: "POST", body: { addressee_id: u.id } }); toast("Запрос отправлен", "ok"); }
            catch (err) { toast(err.message, "error"); e.target.disabled = false; }
          }}, "+ В друзья"),
        ));
      }
    } catch (e) { toast(e.message, "error"); }
  }, 300));

  const pendingBox = el("div");
  const friendsBox = el("div");

  async function loadAll() {
    try {
      const [pending, friends] = await Promise.all([
        api("/api/v1/users/friends/pending"),
        api("/api/v1/users/friends/list"),
      ]);
      clear(pendingBox);
      pendingBox.append(el("h2", {}, "Входящие запросы"));
      if (!pending.length) pendingBox.append(el("div", { class: "empty" }, "Нет новых запросов"));
      for (const p of pending) {
        pendingBox.append(el("div", { class: "user-row" },
          el("div", {},
            el("div", { class: "name" }, p.username),
            el("div", { class: "id" }, shortId(p.requester_id)),
          ),
          el("button", { onclick: async (e) => {
            e.target.disabled = true;
            try { await api(`/api/v1/users/friends/${p.friendship_id}/accept`, { method: "PATCH" }); toast("Принято", "ok"); loadAll(); }
            catch (err) { toast(err.message, "error"); e.target.disabled = false; }
          }}, "Принять"),
        ));
      }
      clear(friendsBox);
      friendsBox.append(el("h2", {}, "Мои друзья"));
      if (!friends.length) friendsBox.append(el("div", { class: "empty" }, "Друзей пока нет"));
      for (const f of friends) {
        state.usernameCache[f.id] = f.username;
        friendsBox.append(el("div", { class: "user-row" },
          el("div", {},
            el("div", { class: "name" }, f.username),
            el("div", { class: "id" }, f.email),
          ),
          el("span", { class: "id" }, "✓ друг"),
        ));
      }
    } catch (e) { toast(e.message, "error"); }
  }

  wrapper.append(
    meBox,
    el("div", { class: "toolbar" }, el("h2", {}, "Найти друга"), search),
    searchResults,
    pendingBox,
    friendsBox,
  );
  loadAll();
  return wrapper;
}

// ----------------- Matches -----------------
function viewMatches() {
  const wrapper = el("div");
  const grid = el("div", { class: "films" }, el("div", { class: "empty" }, "Загрузка..."));
  wrapper.append(el("div", { class: "toolbar" }, el("h2", {}, "Совпадения с друзьями")), grid);
  (async () => {
    try {
      const matches = await api("/api/v1/matches");
      clear(grid);
      if (!matches.length) {
        grid.append(el("div", { class: "empty" }, "Нет совпадений. Подружись с кем-то и добавьте общие фильмы в «Хочу посмотреть»."));
        return;
      }
      for (const m of matches) {
        const card = filmCard(m.film, "match");
        const usernames = await Promise.all(m.matched_friend_ids.map(fetchUsername));
        card.insertBefore(
          el("div", { class: "meta" }, "В списке у: " + usernames.join(", ")),
          card.querySelector(".desc"),
        );
        const btn = el("button", { onclick: async () => {
          try {
            const s = await api("/api/v1/sessions", { method: "POST", body: { film_id: m.film.id, invited_user_ids: m.matched_friend_ids } });
            location.hash = "#watch/" + s.session_id;
          } catch (e) { toast(e.message, "error"); }
        }}, "▶ Смотреть вместе");
        card.querySelector(".actions").innerHTML = "";
        card.querySelector(".actions").append(btn);
        grid.append(card);
      }
    } catch (e) { toast(e.message, "error"); }
  })();
  return wrapper;
}

// ----------------- Notifications -----------------
function viewNotifications() {
  const wrapper = el("div");
  const list = el("div", {}, el("div", { class: "empty" }, "Загрузка..."));
  wrapper.append(
    el("div", { class: "toolbar" },
      el("h2", {}, "Уведомления"),
      el("button", { class: "ghost", onclick: async () => {
        try { await api("/api/v1/notifications/read", { method: "POST" }); state.unread = 0; render(); }
        catch (e) { toast(e.message, "error"); }
      }}, "Отметить все как прочитанные"),
    ),
    list,
  );
  (async () => {
    try {
      const data = await api("/api/v1/notifications?limit=100");
      clear(list);
      if (!data.items.length) { list.append(el("div", { class: "empty" }, "Уведомлений пока нет.")); return; }
      for (const n of data.items) {
        list.append(await renderNotification(n));
      }
    } catch (e) { toast(e.message, "error"); }
  })();
  return wrapper;
}

async function renderNotification(n) {
  const date = new Date(n.created_at).toLocaleString();
  let line, action;
  if (n.kind === "friend.request") {
    const username = await fetchUsername(n.payload.requester_id);
    line = `${username} хочет добавить тебя в друзья`;
    action = el("a", { href: "#friends" }, "Перейти");
  } else if (n.kind === "friend.accepted") {
    const username = await fetchUsername(n.payload.addressee_id);
    line = `${username} принял твой запрос дружбы`;
  } else if (n.kind === "session.created") {
    const username = await fetchUsername(n.payload.host_id);
    line = `${username} зовёт смотреть фильм вместе`;
    action = el("a", { href: "#watch/" + n.payload.session_id }, "Присоединиться");
  } else {
    line = n.kind;
  }
  return el("div", { class: "user-row" },
    el("div", {},
      el("div", { class: "name" }, line),
      el("div", { class: "id" }, date),
    ),
    action || "",
  );
}

function startNotifPolling() {
  if (state.notifTimer) clearInterval(state.notifTimer);
  const tick = async () => {
    try {
      const data = await api("/api/v1/notifications?limit=1");
      if (data.unread !== state.unread) {
        state.unread = data.unread;
        if (!location.hash.startsWith("#watch/")) render();
      }
    } catch {}
  };
  tick();
  state.notifTimer = setInterval(tick, 5000);
}

// ----------------- Watch -----------------
function viewWatch(sessionId) {
  if (state.ws) try { state.ws.close(); } catch {}

  // Контейнер, в который воткнём либо <video>, либо YouTube iframe.
  const playerHost = el("div", { class: "player-host" });
  // Унифицированное API над плеером: реализуется по-разному для html5/YT,
  // но снаружи код один. Null до завершения загрузки.
  let playerCtl = null;
  // Локальный публикатор play/pause/seek в WS. Перепишется на боевую
  // реализацию когда WS готов; до тех пор тихо игнорируем.
  let publishLocal = () => {};

  const sessionLabel = el("span", { class: "session-id" }, sessionId);
  const partsLabel = el("span", { class: "participants" }, "Участники: загрузка...");
  const copyBtn = el("button", { class: "ghost", onclick: () => {
    navigator.clipboard.writeText(location.href);
    toast("Ссылка скопирована — отправь другу", "ok");
  }}, "🔗 Копировать ссылку");
  const leaveBtn = el("button", { class: "ghost danger", onclick: () => {
    if (state.ws) try { state.ws.close(); } catch {}
    state.ws = null;
    location.hash = "#catalog";
  }}, "Выйти");

  const playerPane = el("div", { class: "player-pane" },
    playerHost,
    el("div", { class: "player-info" }, partsLabel, sessionLabel, copyBtn, leaveBtn),
  );

  const messages = el("div", { class: "messages" });
  const chatInput = el("input", { placeholder: "Написать сообщение…", onkeydown: (e) => { if (e.key === "Enter") sendChat(); } });
  const chatSend = el("button", { onclick: sendChat }, "Отправить");
  function sendChat() {
    const text = chatInput.value.trim();
    if (!text || !state.ws || state.ws.readyState !== 1) return;
    state.ws.send(JSON.stringify({ type: "chat", text }));
    chatInput.value = "";
  }
  const chatPane = el("aside", { class: "chat-pane" },
    el("header", {}, el("span", { class: "title" }, "Чат")),
    messages,
    el("footer", {}, chatInput, chatSend),
  );

  // ---- Factories: html5 video & YouTube IFrame Player ----

  function makeHtml5Player(url) {
    const video = el("video", { controls: true, src: url, preload: "metadata" });
    playerHost.replaceChildren(video);

    const ctl = {
      play() {
        state.applyingRemote = true;
        video.play().catch(() => {});
        setTimeout(() => state.applyingRemote = false, 200);
      },
      pause() {
        state.applyingRemote = true;
        video.pause();
        setTimeout(() => state.applyingRemote = false, 200);
      },
      seek(t) {
        state.applyingRemote = true;
        video.currentTime = t;
        setTimeout(() => state.applyingRemote = false, 200);
      },
      getPos() { return video.currentTime || 0; },
    };

    // Локальные действия пользователя → публикуем в WS (если не remote).
    video.addEventListener("play",  () => publishLocal("play",  video.currentTime));
    video.addEventListener("pause", () => publishLocal("pause", video.currentTime));
    let lastSeek = 0;
    video.addEventListener("seeked", () => {
      const now = Date.now();
      if (now - lastSeek < 200) return; // dedupe
      lastSeek = now;
      publishLocal("seek", video.currentTime);
    });

    return ctl;
  }

  async function makeYouTubePlayer(videoId) {
    // YT.Player заменит этот div на <iframe>. Контейнер обёртка нужна, чтобы
    // CSS-правило .youtube-embed применилось к итоговому iframe (см. onReady).
    const host = el("div", {});
    playerHost.replaceChildren(host);
    const YT = await loadYouTubeApi();

    return await new Promise((resolve) => {
      const player = new YT.Player(host, {
        videoId,
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1 },
        events: {
          onReady: () => {
            const iframe = player.getIframe && player.getIframe();
            if (iframe) iframe.className = "youtube-embed";

            // Seek-детект: YouTube API не шлёт явного "seeked" события.
            // Раз в 500мс сверяем текущую позицию с ожидаемой (prev + dt
            // если playing). Прыжок > 1 секунды считаем seek'ом.
            let prevPos = 0, prevTs = Date.now(), prevState = -1;
            setInterval(() => {
              if (state.applyingRemote) {
                prevPos = player.getCurrentTime();
                prevTs = Date.now();
                prevState = player.getPlayerState();
                return;
              }
              const ps = player.getPlayerState();
              const pos = player.getCurrentTime();
              const now = Date.now();
              if (prevState === YT.PlayerState.PLAYING) {
                const expected = prevPos + (now - prevTs) / 1000;
                if (Math.abs(pos - expected) > 1.0) {
                  publishLocal("seek", pos);
                }
              }
              prevPos = pos; prevTs = now; prevState = ps;
            }, 500);

            resolve({
              play() {
                state.applyingRemote = true;
                player.playVideo();
                setTimeout(() => state.applyingRemote = false, 400);
              },
              pause() {
                state.applyingRemote = true;
                player.pauseVideo();
                setTimeout(() => state.applyingRemote = false, 400);
              },
              seek(t) {
                state.applyingRemote = true;
                player.seekTo(t, true);
                setTimeout(() => state.applyingRemote = false, 400);
              },
              getPos() {
                try { return player.getCurrentTime() || 0; } catch { return 0; }
              },
            });
          },
          onStateChange: (ev) => {
            if (ev.data === YT.PlayerState.PLAYING) {
              publishLocal("play",  player.getCurrentTime());
            } else if (ev.data === YT.PlayerState.PAUSED) {
              publishLocal("pause", player.getCurrentTime());
            }
          },
        },
      });
    });
  }

  // ---- Load session + chat history, then construct the right player ----
  (async () => {
    try {
      const session = await api(`/api/v1/sessions/${sessionId}`);
      // Подтягиваем фильм, чтобы взять video_url. Локальные пути вида
      // "/videos/foo.mp4" обслуживает nginx; YouTube ссылки идут в IFrame API.
      let videoUrl = DEMO_VIDEO;
      try {
        const film = await api(`/api/v1/films/${session.film_id}`);
        videoUrl = film.video_url || DEMO_VIDEO;
      } catch { /* fallback to DEMO_VIDEO */ }

      const ytId = parseYouTubeId(videoUrl);
      playerCtl = ytId
        ? await makeYouTubePlayer(ytId)
        : makeHtml5Player(videoUrl);

      const usernames = await Promise.all(session.participants.map(fetchUsername));
      partsLabel.textContent = "Участники: " + usernames.join(", ");
      const history = await api(`/api/v1/sessions/${sessionId}/chat`);
      for (const m of history) await appendChat(m, false);

      // Apply current playback state — единый интерфейс для обоих режимов.
      if (session.position) playerCtl.seek(session.position);
      if (session.state === "playing") {
        try { playerCtl.play(); } catch {}
      }
    } catch (e) { toast("Не удалось загрузить сессию: " + e.message, "error"); }
    connectWS();
  })();

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    // Токен НЕ в query string — он бы утёк в access-логи nginx, в историю
    // браузера и в Referer. Шлём его первым сообщением после открытия.
    const url = `${proto}//${location.host}/ws/${sessionId}`;
    state.ws = new WebSocket(url);
    state.ws.onopen = () => {
      try {
        state.ws.send(JSON.stringify({ type: "auth", token: state.token }));
      } catch {}
      appendSystem("вы подключились");
    };
    state.ws.onclose = () => appendSystem("соединение закрыто");
    state.ws.onerror = () => toast("WebSocket ошибка", "error");
    state.ws.onmessage = async (ev) => {
      const msg = JSON.parse(ev.data);
      const username = msg.user_id ? await fetchUsername(msg.user_id) : "";
      if (msg.type === "play") {
        if (playerCtl) {
          if (Math.abs(playerCtl.getPos() - msg.position) > 0.5) playerCtl.seek(msg.position);
          playerCtl.play();
        }
        appendSystem(`${username} включил воспроизведение`);
      } else if (msg.type === "pause") {
        if (playerCtl) {
          if (Math.abs(playerCtl.getPos() - msg.position) > 0.5) playerCtl.seek(msg.position);
          playerCtl.pause();
        }
        appendSystem(`${username} поставил на паузу`);
      } else if (msg.type === "seek") {
        if (playerCtl) playerCtl.seek(msg.position);
        appendSystem(`${username} перемотал на ${Math.round(msg.position)}с`);
      } else if (msg.type === "chat") {
        await appendChat(msg, true);
      } else if (msg.type === "join") {
        if (msg.session) {
          const usernames = await Promise.all(msg.session.participants.map(fetchUsername));
          partsLabel.textContent = "Участники: " + usernames.join(", ");
        }
        appendSystem(`${username} присоединился`);
      } else if (msg.type === "leave") {
        appendSystem(`${username} вышел`);
      }
    };
  }

  // Боевая реализация publishLocal — после её установки WS-публикация заработает.
  publishLocal = (type, position) => {
    if (state.applyingRemote || !state.ws || state.ws.readyState !== 1) return;
    state.ws.send(JSON.stringify({ type, position }));
  };

  async function appendChat(msg, scroll) {
    const username = await fetchUsername(msg.user_id);
    const avatar = el("div", { class: "avatar", style: `background: ${avatarColor(msg.user_id)}` },
      (username[0] || "?").toUpperCase());
    const body = el("div", { class: "body" },
      el("div", { class: "who" }, username),
      msg.text);
    messages.append(el("div", { class: "msg" }, avatar, body));
    if (scroll) messages.scrollTop = messages.scrollHeight;
  }
  function appendSystem(text) {
    messages.append(el("div", { class: "msg system" }, el("div", { class: "body" }, text)));
    messages.scrollTop = messages.scrollHeight;
  }

  return el("div", { class: "watch" }, playerPane, chatPane);
}

// ----------------- Helpers -----------------
function debounce(fn, ms) {
  let t;
  return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
}
