# AgentPulse — official site (agentpulse.cc)

Static, zero-build marketing site (HTML/CSS/JS). Dark "operations cockpit"
aesthetic with the teal **pulse** brand signal, an animated pulse-network canvas,
and a live group-chat demo. No dependencies, no build step.

## Local preview

Any static server works:

```bash
cd apps/site
python3 -m http.server 4000
# open http://localhost:4000
```

## Deploy to Vercel (auto-deploy on push)

The repo is on GitHub, so use Vercel's native Git integration — every push to
the default branch redeploys automatically:

1. Vercel → **Add New… → Project** → import `Clycheng/agentpulse`.
2. **Root Directory** → `apps/site`.
3. **Framework Preset** → **Other** (it's static; no build command, no output dir).
4. **Deploy.** From then on, every push that touches `apps/site` auto-deploys.

### Custom domain

In the Vercel project → **Settings → Domains** → add `agentpulse.cc` (and
`www.agentpulse.cc`), then point the domain's DNS at Vercel as instructed
(A record `76.76.21.21` for the apex, or a CNAME to `cname.vercel-dns.com`).

## Files

- `index.html` — page structure + copy (English)
- `styles.css` — full design system + sections + responsive + reduced-motion
- `main.js` — pulse-network canvas, scroll reveal, nav, live chat demo
- `favicon.svg` — brand mark
- `vercel.json` — clean URLs + security headers
