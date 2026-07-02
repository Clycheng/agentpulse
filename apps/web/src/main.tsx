import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowRight, Radar, Sparkles, Zap } from 'lucide-react';
import './styles.css';

function App() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="/">
          <Activity aria-hidden="true" />
          <span>IntentPulse</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#platform">Platform</a>
          <a href="#signals">Signals</a>
          <a href="#contact">Contact</a>
        </nav>
      </header>

      <section className="hero" id="platform">
        <div className="hero-content">
          <p className="eyebrow">Customer intent intelligence</p>
          <h1>IntentPulse</h1>
          <p className="hero-copy">
            Turn fragmented product, sales, and support signals into clear next
            actions for growth teams.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#contact">
              Request access
              <ArrowRight aria-hidden="true" />
            </a>
            <a className="secondary-action" href="#signals">
              Explore signals
            </a>
          </div>
        </div>
        <div className="product-preview">
          <img
            src="/product-preview.svg"
            alt="IntentPulse product dashboard preview"
          />
          <div className="insight-row">
            <Sparkles aria-hidden="true" />
            <p>Expansion motion detected across 12 active accounts.</p>
          </div>
        </div>
      </section>

      <section className="section" id="signals">
        <div className="section-heading">
          <p className="eyebrow">Signal stack</p>
          <h2>Built for fast GTM decisions</h2>
        </div>
        <div className="feature-grid">
          <article>
            <Radar aria-hidden="true" />
            <h3>Detect intent</h3>
            <p>Unify website activity, CRM changes, and product events.</p>
          </article>
          <article>
            <Zap aria-hidden="true" />
            <h3>Prioritize action</h3>
            <p>Score urgency and recommend the next best team workflow.</p>
          </article>
          <article>
            <Activity aria-hidden="true" />
            <h3>Track outcomes</h3>
            <p>Measure which motions create pipeline and retention lift.</p>
          </article>
        </div>
      </section>

      <section className="contact-band" id="contact">
        <div>
          <p className="eyebrow">Early access</p>
          <h2>Bring your customer signals into focus.</h2>
        </div>
        <a className="primary-action dark" href="mailto:hello@intentpulse.dev">
          hello@intentpulse.dev
        </a>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
