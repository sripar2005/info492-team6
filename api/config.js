// Gives the browser the public Supabase settings from Vercel's environment variables.
// SUPABASE_ANON_KEY is the public (anon / publishable) key, made to be used in browsers; row-level security
// in supabase/migrations decides what each signed-in person can read or write. Never put the service_role key here.
module.exports = function handler(req, res) {
  const url = process.env.SUPABASE_URL || '';
  const anonKey = process.env.SUPABASE_ANON_KEY || '';
  res.setHeader('Cache-Control', 'no-store');
  res.status(200).json({ configured: Boolean(url && anonKey), url, anonKey });
};
