/* The sample project, run entirely in this browser tab.
   Same calls as the Supabase client the live record uses, so every screen works the same way.
   Nothing is sent anywhere and nothing is saved: reload the page and the sample starts over. */
(function () {
  'use strict';
  var NEXT = { sub: 'gc', gc: 'architect', architect: 'owner' }, PREV = { owner: 'architect', architect: 'gc', gc: 'sub' };
  var USER = { id: 'sample-user', email: 'sample@clausestream.demo' };

  function make() {
    var db = { projects: [], members: [], invites: [], documents: [], pieces: [], links: [], threads: [], events: [] }, seq = 1;
    function now() { return new Date().toISOString(); }
    function cmp(a, b) { return a === b ? 0 : (a == null ? -1 : b == null ? 1 : (typeof a === 'number' && typeof b === 'number') ? a - b : String(a).localeCompare(String(b), 'en', { numeric: true })); }

    function Q(t) { this.t = t; this.f = []; this.op = 'select'; this.sing = false; }
    Q.prototype.select = function () { return this; };
    Q.prototype.eq = function (k, v) { this.f.push(function (r) { return String(r[k]) === String(v); }); return this; };
    Q.prototype.neq = function (k, v) { this.f.push(function (r) { return String(r[k]) !== String(v); }); return this; };
    Q.prototype.in = function (k, arr) { this.f.push(function (r) { return arr.map(String).indexOf(String(r[k])) >= 0; }); return this; };
    Q.prototype.or = function (str) {
      var alts = str.split(',').map(function (x) { var p = x.split('.'); return [p[0], p.slice(2).join('.')]; });
      this.f.push(function (r) { return alts.some(function (a) { return String(r[a[0]]) === a[1]; }); }); return this;
    };
    Q.prototype.textSearch = function (col, text) {
      var words = String(text).toLowerCase().replace(/["()]/g, ' ').split(/\s+/).filter(function (w) { return w && w !== 'or' && w !== 'and'; });
      this.f.push(function (r) { var s = ((r.section || '') + ' ' + (r.body || '')).toLowerCase(); return words.every(function (w) { return w.charAt(0) === '-' ? s.indexOf(w.slice(1)) < 0 : s.indexOf(w) >= 0; }); });
      return this;
    };
    Q.prototype.order = function (k, o) { this.ord = [k, !(o && o.ascending === false)]; return this; };
    Q.prototype.limit = function (n) { this.lim = n; return this; };
    Q.prototype.single = function () { this.sing = true; return this; };
    Q.prototype.maybeSingle = Q.prototype.single;
    Q.prototype.insert = function (r) { this.op = 'insert'; this.rows = [].concat(r); return this; };
    Q.prototype.update = function (r) { this.op = 'update'; this.patch = r; return this; };
    Q.prototype.delete = function () { this.op = 'delete'; return this; };
    Q.prototype.then = function (ok, no) { var self = this; return Promise.resolve().then(function () { return self.run(); }).then(ok, no); };
    Q.prototype.run = function () {
      var T = db[this.t], self = this, match = function (r) { return self.f.every(function (fn) { return fn(r); }); };
      if (this.op === 'insert') {
        var out = this.rows.map(function (r) {
          var x = Object.assign({ id: seq++, created_at: now(), updated_at: now() }, JSON.parse(JSON.stringify(r)));
          if (self.t === 'threads') { x.status = x.status || 'draft'; x.holder = x.holder || 'sub'; }
          if (self.t === 'projects') db.members.push({ project_id: x.id, user_id: USER.id, party: 'gc', is_admin: true });
          T.push(x);
          if (self.t === 'events') advance(x);
          return x;
        });
        return { data: this.sing ? out[0] : out, error: null };
      }
      if (this.op === 'update') { T.filter(match).forEach(function (r) { Object.assign(r, self.patch, { updated_at: now() }); }); return { data: null, error: null }; }
      if (this.op === 'delete') { db[this.t] = T.filter(function (r) { return !match(r); }); return { data: null, error: null }; }
      var rows = T.filter(match);
      if (this.ord) { var k = this.ord[0], up = this.ord[1]; rows = rows.slice().sort(function (a, b) { return up ? cmp(a[k], b[k]) : cmp(b[k], a[k]); }); }
      if (this.lim) rows = rows.slice(0, this.lim);
      rows = JSON.parse(JSON.stringify(rows));
      if (this.sing) return rows.length ? { data: rows[0], error: null } : { data: null, error: { message: 'Not found in the sample project.' } };
      return { data: rows, error: null };
    };
    // Same rule as the database trigger: sending, returning and deciding move the thread.
    function advance(e) {
      var th = db.threads.filter(function (t) { return String(t.id) === String(e.thread_id); })[0]; if (!th) return;
      if (e.kind === 'submit' && NEXT[e.party]) { th.holder = NEXT[e.party]; th.status = 'with_' + NEXT[e.party]; }
      if (e.kind === 'return' && PREV[e.party]) { th.holder = PREV[e.party]; th.status = 'returned'; }
      if (e.kind === 'approve' && e.party === 'owner') th.status = 'approved';
      if (e.kind === 'reject' && e.party === 'owner') th.status = 'rejected';
      th.updated_at = now();
    }
    return {
      sample: true,
      from: function (t) { if (!db[t]) db[t] = []; return new Q(t); },
      rpc: function (name, args) {
        if (name === 'project_people') return Promise.resolve({ data: db.members.filter(function (m) { return String(m.project_id) === String(args.p); }).map(function (m) { return Object.assign({ email: 'You (sample)' }, m); }), error: null });
        return Promise.resolve({ data: 0, error: null });
      },
      auth: {
        onAuthStateChange: function () {},
        getSession: function () { return Promise.resolve({ data: { session: { user: USER } } }); },
        signInWithOtp: function () { return Promise.resolve({ data: {}, error: null }); },
        signOut: function () { return Promise.resolve({}); }
      }
    };
  }
  window.CSDemo = { make: make, user: USER };
})();
