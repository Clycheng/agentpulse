import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Bell, LayoutDashboard, Search, Settings } from 'lucide-react';
import './styles.css';

function App() {
  return (
    <main className="desktop-shell">
      <aside className="sidebar">
        <div className="brand-mark">IP</div>
        <button aria-label="Dashboard">
          <LayoutDashboard aria-hidden="true" />
        </button>
        <button aria-label="Search">
          <Search aria-hidden="true" />
        </button>
        <button aria-label="Notifications">
          <Bell aria-hidden="true" />
        </button>
        <button aria-label="Settings">
          <Settings aria-hidden="true" />
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>IntentPulse Desktop</p>
            <h1>Command Center</h1>
          </div>
          <button className="sync-button">Sync signals</button>
        </header>

        <section className="dashboard-grid">
          <article className="summary">
            <span>Priority accounts</span>
            <strong>24</strong>
            <p>8 moved into high intent this week.</p>
          </article>
          <article className="summary">
            <span>Open tasks</span>
            <strong>41</strong>
            <p>12 are ready for sales handoff.</p>
          </article>
          <article className="summary">
            <span>Signal health</span>
            <strong>96%</strong>
            <p>All core connectors are reporting.</p>
          </article>
        </section>

        <section className="activity-panel">
          <div className="panel-heading">
            <h2>Live intent feed</h2>
            <span>Updated now</span>
          </div>
          {[
            ['Acme Ops', 'Viewed pricing and invited a new admin'],
            ['Northstar AI', 'Usage spike across reporting workflow'],
            ['Harbor Labs', 'Support sentiment recovered after fix'],
          ].map(([account, detail]) => (
            <div className="feed-row" key={account}>
              <span />
              <div>
                <strong>{account}</strong>
                <p>{detail}</p>
              </div>
            </div>
          ))}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
