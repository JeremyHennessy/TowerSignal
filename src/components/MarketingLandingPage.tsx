import { useState, type FormEvent } from 'react'

type MarketingSection = 'platform' | 'workflow' | 'markets' | 'audience' | 'book-demo'

const asset = (name: string) => `${import.meta.env.BASE_URL}marketing/${name}`

function scrollToSection(section: MarketingSection) {
  document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function MarketingLandingPage() {
  const [demoSubmitted, setDemoSubmitted] = useState(false)

  const submitDemo = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setDemoSubmitted(true)
  }

  return <main className="marketing-page">
    <header className="marketing-nav">
      <button className="marketing-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="TowerSignal home">
        <img src={asset('towersignal-logo.webp')} alt="TowerSignal" />
      </button>
      <nav className="marketing-nav-links" aria-label="Marketing navigation">
        <button type="button" onClick={() => scrollToSection('platform')}>Platform</button>
        <button type="button" onClick={() => scrollToSection('workflow')}>How it works</button>
        <button type="button" onClick={() => scrollToSection('markets')}>Markets</button>
        <button type="button" onClick={() => scrollToSection('audience')}>Who it’s for</button>
      </nav>
      <div className="marketing-nav-actions">
        <a className="marketing-login" href="#/login">Log in</a>
        <button className="marketing-demo-button" type="button" onClick={() => scrollToSection('book-demo')}>Book a demo</button>
      </div>
    </header>

    <section className="marketing-hero" aria-labelledby="marketing-hero-title">
      <div className="marketing-hero-copy">
        <span className="marketing-kicker"><i /> Property, compliance &amp; service intelligence</span>
        <h1 id="marketing-hero-title">Find the buildings that <em>need you next.</em></h1>
        <p>TowerSignal turns fragmented public records into actionable property intelligence for water-treatment companies, cooling-tower service providers, consultants and field teams.</p>
        <div className="marketing-hero-actions">
          <button className="marketing-primary" type="button" onClick={() => scrollToSection('book-demo')}>Book a demo <span aria-hidden="true">→</span></button>
          <a className="marketing-secondary" href="#/login">Log in to TowerSignal</a>
        </div>
        <div className="marketing-market-line" aria-label="TowerSignal market coverage">
          <span>New York City</span><span>New York State</span><span>Toronto expansion</span>
        </div>
      </div>

      <div className="marketing-hero-product" aria-label="TowerSignal product preview">
        <div className="marketing-browser marketing-browser-main">
          <div className="marketing-browser-bar"><i /><i /><i /><span>app.towersignal</span></div>
          <img src={asset('towersignal-prospect-mobile.svg')} alt="TowerSignal Prospect workspace showing prioritized cooling-tower accounts" />
        </div>
        <div className="marketing-float-card marketing-float-card-top"><small>PRIORITY SIGNAL</small><strong>Why this property, why now</strong><span>Recent public-record activity stays attached to the account.</span></div>
        <div className="marketing-float-card marketing-float-card-bottom"><small>RELATIONSHIPS</small><strong>Owner + contractor context</strong><span>Move from a building to the people and companies around it.</span></div>
      </div>
    </section>

    <section className="marketing-brand-banner" aria-label="TowerSignal brand">
      <img src={asset('towersignal-hero.webp')} alt="TowerSignal" />
      <div><span>One searchable workspace</span><strong>Property. Compliance. Relationships. Opportunity.</strong></div>
    </section>

    <section className="marketing-statement" id="platform">
      <span className="marketing-eyebrow">THE PLATFORM</span>
      <h2>Public records weren’t built for sales and service teams. TowerSignal is.</h2>
      <p>Instead of searching agency portals, spreadsheets, deeds, violations, procurement records and source documents one at a time, TowerSignal connects them around the property and turns observable changes into an explainable reason to act.</p>
    </section>

    <section className="marketing-capability-grid" aria-label="TowerSignal capabilities">
      <article><span className="marketing-cap-number">01</span><h3>Property intelligence</h3><p>Search buildings, equipment and account profiles from a single property-centered workspace.</p><strong>Map → profile → source</strong></article>
      <article><span className="marketing-cap-number">02</span><h3>Compliance &amp; maintenance signals</h3><p>Track violations, inspections, sampling gaps and other observable conditions that can change account priority.</p><strong>Change → timing signal</strong></article>
      <article><span className="marketing-cap-number">03</span><h3>Ownership &amp; relationships</h3><p>Understand defensible ownership, management, contractor, consultant and public-customer relationships.</p><strong>Property → people → companies</strong></article>
      <article><span className="marketing-cap-number">04</span><h3>Service opportunities</h3><p>Prioritize high-value buildings and keep the evidence, notes, watchlists and next action beside the lead.</p><strong>Signal → action</strong></article>
    </section>

    <section className="marketing-product-story">
      <div className="marketing-product-copy">
        <span className="marketing-eyebrow">PROSPECT</span>
        <h2>Start with the accounts that have a reason to call now.</h2>
        <p>Filter the market by priority, cooling-tower status, violations, sampling follow-up, recent property activity and other account criteria. The goal is a smaller, explainable working set—not another giant spreadsheet.</p>
        <ul><li>Map and market-wide screening</li><li>Deterministic priority signals</li><li>Fast drill-through to source evidence</li></ul>
      </div>
      <div className="marketing-product-frame marketing-frame-light"><img src={asset('towersignal-prospect-mobile.svg')} alt="TowerSignal Prospect workspace" /></div>
    </section>

    <section className="marketing-product-story marketing-product-story-reverse">
      <div className="marketing-product-copy">
        <span className="marketing-eyebrow">PROPERTY PROFILE</span>
        <h2>See the property, the signal and the source trail together.</h2>
        <p>Open a building to understand equipment, ownership, violations, maintenance signals, linked documents and account workflow without losing the evidence that made the property interesting.</p>
        <ul><li>Property and equipment context</li><li>Ownership and contractor relationships</li><li>Source documents and historical activity</li></ul>
      </div>
      <div className="marketing-product-frame marketing-frame-dark"><img src={asset('towersignal-account-mobile.svg')} alt="TowerSignal property account profile" /></div>
    </section>

    <section className="marketing-workflow" id="workflow">
      <div className="marketing-workflow-heading"><span className="marketing-eyebrow">HOW IT WORKS</span><h2>From fragmented source data to a defensible next action.</h2><p>TowerSignal keeps collection, identity resolution, prioritization and evidence separate so a useful signal does not become an unexplained score.</p></div>
      <div className="marketing-process-grid">
        <article><span>1</span><div><h3>Collect</h3><p>Bring together public cooling-tower, building, property, ownership and procurement records.</p></div></article>
        <article><span>2</span><div><h3>Connect</h3><p>Normalize records around properties and link identities only where the evidence supports the relationship.</p></div></article>
        <article><span>3</span><div><h3>Prioritize</h3><p>Use observable account conditions and recent changes to surface service and compliance opportunities.</p></div></article>
        <article><span>4</span><div><h3>Act + verify</h3><p>Prepare for outreach or a site visit with the source trail, notes, documents and next action in one place.</p></div></article>
      </div>
    </section>

    <section className="marketing-evidence">
      <div className="marketing-evidence-copy"><span className="marketing-eyebrow">EVIDENCE FIRST</span><h2>Know why a signal exists.</h2><p>Every useful commercial signal should be traceable to the public record behind it. TowerSignal is designed to expose source evidence and keep uncertainty visible instead of manufacturing a relationship.</p></div>
      <div className="marketing-source-stack" aria-label="Example TowerSignal source families">
        <div><strong>Cooling-tower records</strong><span>Registrations, inspections and equipment context</span></div>
        <div><strong>Building &amp; compliance</strong><span>DOB, OATH and related property activity</span></div>
        <div><strong>Ownership &amp; property</strong><span>Recorded property changes, deeds and ownership evidence</span></div>
        <div><strong>Procurement</strong><span>Solicitations, awards, contracts, buyers and observed vendors</span></div>
      </div>
    </section>

    <section className="marketing-markets" id="markets">
      <div className="marketing-section-heading"><span className="marketing-eyebrow">MARKETS</span><h2>Built market by market, around the best available public evidence.</h2><p>The source model changes by jurisdiction. TowerSignal keeps the workflow consistent while expanding the evidence graph underneath it.</p></div>
      <div className="marketing-market-grid">
        <article className="marketing-market-featured"><span>CORE MARKET</span><h3>New York City</h3><p>Cooling-tower registrations and inspections joined to building, violation, property, ownership, procurement and workflow intelligence.</p></article>
        <article><span>EXPANDED CONTEXT</span><h3>New York State</h3><p>Statewide tower registry and public-authority procurement context extend account and vendor intelligence beyond NYC.</p></article>
        <article><span>EXPANSION</span><h3>Toronto</h3><p>A growing Toronto property and source-document intelligence model designed around the same evidence-first workflow.</p></article>
      </div>
    </section>

    <section className="marketing-audience" id="audience">
      <div className="marketing-section-heading"><span className="marketing-eyebrow">WHO IT’S FOR</span><h2>For the teams closest to complex building water systems.</h2></div>
      <div className="marketing-audience-grid">
        <article><span>WT</span><h3>Water-treatment companies</h3><p>Prioritize accounts, understand recent signals and bring property evidence into account planning.</p></article>
        <article><span>CT</span><h3>Cooling-tower service providers</h3><p>Find high-value buildings where equipment, compliance or maintenance context creates a reason for attention.</p></article>
        <article><span>CE</span><h3>Consultants &amp; engineers</h3><p>Review property history, source documents and relationships before recommendations, inspections or site work.</p></article>
        <article><span>FT</span><h3>Field &amp; service teams</h3><p>Prepare for site visits with the building, equipment, contacts, documents and recent activity already assembled.</p></article>
      </div>
    </section>

    <section className="marketing-demo" id="book-demo">
      <div className="marketing-demo-copy">
        <span className="marketing-eyebrow">BOOK A DEMO</span>
        <h2>See TowerSignal with the market and workflow that matter to your team.</h2>
        <p>Tell us who you are and what you want to evaluate. We can connect this form to email delivery later; for now it is a complete front-end contact sheet only.</p>
        <div className="marketing-demo-points"><span>NYC cooling-tower intelligence</span><span>Property &amp; relationship drill-through</span><span>Compliance and service-opportunity workflow</span><span>Toronto expansion preview</span></div>
      </div>
      <form className="marketing-demo-form" onSubmit={submitDemo}>
        <div className="marketing-form-row"><label>Full name<input name="name" type="text" autoComplete="name" minLength={2} required /></label><label>Work email<input name="email" type="email" autoComplete="email" required /></label></div>
        <div className="marketing-form-row"><label>Company<input name="company" type="text" autoComplete="organization" minLength={2} required /></label><label>Role<input name="role" type="text" autoComplete="organization-title" /></label></div>
        <label>Market<select name="market" defaultValue="New York City"><option>New York City</option><option>New York State</option><option>Toronto</option><option>Other / multiple markets</option></select></label>
        <label>What would you like to see?<textarea name="message" rows={4} placeholder="Tell us about your team, territory, accounts or workflow." /></label>
        <button className="marketing-primary marketing-demo-submit" type="submit">Request a demo <span aria-hidden="true">→</span></button>
        {demoSubmitted && <div className="marketing-demo-status" role="status"><strong>Form is ready.</strong><span>Email delivery is not connected yet, so this request has not been sent. The entered details will remain in the form until you leave or refresh this page.</span></div>}
      </form>
    </section>

    <footer className="marketing-footer">
      <img src={asset('towersignal-logo.webp')} alt="TowerSignal" />
      <p>Property, compliance and service-opportunity intelligence for water-service markets.</p>
      <div><a href="#/login">Log in</a><button type="button" onClick={() => scrollToSection('book-demo')}>Book a demo</button></div>
    </footer>
  </main>
}
