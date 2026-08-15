function StudioPromoCard({ onLaunch }) {
  return (
    <div className="studio-promo-card">
      <h3>You know the deal. Now let's plan what comes after it.</h3>

      <p>
        A valuation tells you whether to buy — it doesn't tell you what to build,
        what it'll cost, or whether your layout even works. PropertyIQ Studio picks up
        exactly where this report leaves off: compare this property against others like
        it, then design and budget your build before you break ground.
      </p>

      <div className="studio-promo-features">
        <div className="studio-promo-feature">
          <strong>Similar Property Insights</strong>
          See how this property stacks up against comparable listings on price/sqft —
          so "is this a fair price" has an actual answer.
        </div>
        <div className="studio-promo-feature">
          <strong>Construction Studio</strong>
          Set your plot, pick materials and suppliers, and watch your build cost update
          live as you go.
        </div>
        <div className="studio-promo-feature">
          <strong>Vastu-Checked Layouts</strong>
          Room-by-room compliance guidance built into every plan, not a bolt-on
          disclaimer.
        </div>
        <div className="studio-promo-feature">
          <strong>Share-Ready Plans</strong>
          Export a real, portable plot layout your architect or builder can open
          directly.
        </div>
      </div>

      <button className="studio-cta-btn" onClick={onLaunch}>
        Explore PropertyIQ Studio →
      </button>
    </div>
  );
}

export default StudioPromoCard;
