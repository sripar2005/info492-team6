/* The sample project, run entirely in this browser tab: the same calls as the Supabase client the live platform uses,
   over in-memory tables, with the database's triggers and functions mirrored from assets/rules.js.
   Nothing is sent anywhere and nothing is saved: reload the page and the sample starts over. */
(function (root) {
  'use strict';
  var R = root.CSRules || (typeof require !== 'undefined' ? require('./rules.js') : null);
  var USER = { id: 'sample-user', email: 'sample@clausestream.demo' };
  var TABLES = ['companies', 'company_people', 'projects', 'project_companies', 'invites', 'contracts', 'contract_terms', 'documents', 'pieces', 'links',
    'changes', 'events', 'schedule_versions', 'sov_lines', 'field_links', 'field_submissions'];

  function make() {
    var db = {}, seq = 1, evseq = 1; TABLES.forEach(function (t) { db[t] = []; });
    function now() { return new Date().toISOString(); }
    function uuid() { return 'x' + ('00000' + (seq++).toString(36)).slice(-6); }
    function cmp(a, b) { return a === b ? 0 : (a == null ? -1 : b == null ? 1 : (typeof a === 'number' && typeof b === 'number') ? a - b : String(a).localeCompare(String(b), 'en', { numeric: true })); }
    function copy(x) { return JSON.parse(JSON.stringify(x)); }
    function err(m) { return { data: null, error: { message: m } }; }

    // ---------- triggers (mirroring before_event / after_event in the migration) ----------
    function blocker(x) {
      if (!x.change_id || x.kind !== 'submit') return null;
      var c = db.changes.filter(function (r) { return r.id === x.change_id; })[0];
      return c ? R.sendBlocker(c, db.events) : null;
    }
    function afterEvent(x) {
      if (!x.change_id) return;
      var c = db.changes.filter(function (r) { return r.id === x.change_id; })[0]; if (!c) return;
      var arch = (db.project_companies.filter(function (p) { return p.project_id === c.project_id && p.role === 'architect'; })[0] || {}).company_id || null;
      var n = R.advance(c, x.kind, arch); c.status = n.status; c.holder = n.holder; c.updated_at = now();
      var down = c.tier === 'proposal' && R.flowDown(x.kind);
      if (down) db.changes.forEach(function (r) { if (r.parent_id === c.id) { r.status = down; r.holder = null; r.updated_at = now(); } });
    }

    // ---------- a small query builder, enough for the platform views ----------
    function Q(t) { this.t = t; this.f = []; this.op = 'select'; this.sing = false; }
    Q.prototype.select = function () { return this; };
    Q.prototype.eq = function (k, v) { this.f.push(function (r) { return String(r[k]) === String(v); }); return this; };
    Q.prototype.neq = function (k, v) { this.f.push(function (r) { return String(r[k]) !== String(v); }); return this; };
    Q.prototype.is = function (k, v) { this.f.push(function (r) { return v === null ? r[k] == null : r[k] === v; }); return this; };
    Q.prototype.in = function (k, arr) { var s = arr.map(String); this.f.push(function (r) { return s.indexOf(String(r[k])) >= 0; }); return this; };
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
    Q.prototype.maybeSingle = function () { this.sing = true; this.maybe = true; return this; };
    Q.prototype.insert = function (r) { this.op = 'insert'; this.rows = [].concat(r); return this; };
    Q.prototype.update = function (r) { this.op = 'update'; this.patch = r; return this; };
    Q.prototype.delete = function () { this.op = 'delete'; return this; };
    Q.prototype.then = function (ok, no) { var self = this; return Promise.resolve().then(function () { return self.run(); }).then(ok, no); };
    Q.prototype.run = function () {
      var T = db[this.t], self = this, match = function (r) { return self.f.every(function (fn) { return fn(r); }); };
      if (!T) return err('No table ' + this.t);
      if (this.op === 'insert') {
        if (this.t === 'events') { var bad = this.rows.map(blocker).filter(Boolean)[0]; if (bad) return err(bad); }
        var out = this.rows.map(function (r) {
          var x = copy(r);
          if (self.t === 'events') { x.id = evseq++; if (x.actor === undefined) x.actor = USER.id; x.payload = x.payload || {}; }
          else if (self.t === 'field_links') { x.token = x.token || ('t' + uuid() + Math.random().toString(36).slice(2, 10)); if (x.active === undefined) x.active = true; }
          else if (!x.id && ['company_people', 'project_companies', 'invites'].indexOf(self.t) < 0) x.id = uuid();
          x.created_at = x.created_at || now();
          if (self.t === 'changes') { x.status = x.status || 'draft'; if (x.holder === undefined) x.holder = x.from_company; x.updated_at = x.created_at; x.meta = x.meta || {}; x.cause = x.cause || {}; }
          if (self.t === 'documents') { x.visibility = x.visibility || 'project'; x.meta = x.meta || {}; }
          if (self.t === 'field_submissions') x.status = x.status || 'unverified';
          T.push(x); if (self.t === 'events') afterEvent(x);
          return x;
        });
        return { data: copy(this.sing ? out[0] : out), error: null };
      }
      if (this.op === 'update') {
        if (this.t === 'events') return err('Events can’t be changed.');
        T.filter(match).forEach(function (r) { Object.assign(r, copy(self.patch)); if (self.t === 'changes') r.updated_at = now(); });
        return { data: null, error: null };
      }
      if (this.op === 'delete') { if (this.t === 'events') return err('Events can’t be deleted.'); db[this.t] = T.filter(function (r) { return !match(r); }); return { data: null, error: null }; }
      var rows = T.filter(match);
      if (this.ord) { var k = this.ord[0], up = this.ord[1]; rows = rows.slice().sort(function (a, b) { return up ? cmp(a[k], b[k]) : cmp(b[k], a[k]); }); }
      if (this.lim) rows = rows.slice(0, this.lim);
      rows = copy(rows);
      if (this.sing) return rows.length ? { data: rows[0], error: null } : this.maybe ? { data: null, error: null } : err('Not found in the sample project.');
      return { data: rows, error: null };
    };

    // ---------- functions (mirroring the migration's) ----------
    function company(id) { return db.companies.filter(function (c) { return c.id === id; })[0]; }
    var RPC = {
      start_project: function (a) {
        var pid = uuid(); db.projects.push({ id: pid, name: a.p_name, contract_type: a.p_type, synthetic: !!a.p_synthetic, created_by: USER.id, created_at: now() });
        var cid = uuid(); db.companies.push({ id: cid, name: a.p_company, kind: a.p_role, synthetic: !!a.p_synthetic, created_at: now() });
        db.company_people.push({ company_id: cid, user_id: USER.id, is_admin: true });
        db.project_companies.push({ project_id: pid, company_id: cid, role: a.p_role, is_admin: true });
        return pid;
      },
      add_sample_company: function (a) {
        var cid = uuid(); db.companies.push({ id: cid, name: a.p_name, kind: a.p_kind, trade: a.p_trade || null, synthetic: true, created_at: now() });
        db.company_people.push({ company_id: cid, user_id: USER.id, is_admin: true });
        db.project_companies.push({ project_id: a.p, company_id: cid, role: a.p_kind });
        return cid;
      },
      claim_invites: function () { return 0; },
      project_people: function (a) {
        return db.project_companies.filter(function (pc) { return pc.project_id === a.p; }).map(function (pc) {
          var c = company(pc.company_id);
          return { user_id: USER.id, email: 'you (sample)', company_id: c.id, company: c.name, role: pc.role };
        });
      },
      field_link_info: function (a) {
        var l = db.field_links.filter(function (x) { return x.token === a.p_token && x.active; })[0]; if (!l) return [];
        return [{ project: db.projects.filter(function (p) { return p.id === l.project_id; })[0].name, company: company(l.company_id).name }];
      },
      submit_field: function (a) {
        var l = db.field_links.filter(function (x) { return x.token === a.p_token && x.active; })[0];
        if (!l) throw new Error('This link is no longer active.');
        var body = String(a.p_body || '').trim(); if (body.length < 3) throw new Error('Say what happened in a few words.');
        var recent = db.field_submissions.filter(function (s) { return s.token === l.token && Date.parse(s.created_at) > Date.now() - 36e5; }).length;
        if (recent >= 30) throw new Error('Too many submissions from this link in the last hour. Try again later.');
        var sid = uuid(); db.field_submissions.push({ id: sid, token: l.token, project_id: l.project_id, company_id: l.company_id, body: body, sender_name: String(a.p_name || '').trim() || null, photos: a.p_photos || [], status: 'unverified', created_at: now() });
        db.events.push({ id: evseq++, project_id: l.project_id, change_id: null, company_id: l.company_id, actor: null, kind: 'note', body: 'Field submission received (unverified)', payload: { field_submission: sid }, created_at: now() });
        return sid;
      }
    };
    return {
      sample: true,
      _db: db,
      from: function (t) { return new Q(t); },
      rpc: function (name, args) {
        return Promise.resolve().then(function () { if (!RPC[name]) return err('No function ' + name); try { return { data: RPC[name](args || {}), error: null }; } catch (e) { return err(e.message); } });
      },
      auth: {
        onAuthStateChange: function () {},
        getSession: function () { return Promise.resolve({ data: { session: { user: USER } } }); },
        signInWithOtp: function () { return Promise.resolve({ data: {}, error: null }); },
        signOut: function () { return Promise.resolve({}); }
      }
    };
  }
  var api = { make: make, user: USER };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.CSDemo = api;
})(this);
