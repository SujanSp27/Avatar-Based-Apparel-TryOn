import { Link } from "react-router-dom";
import BrandLogo from "../ui/BrandLogo";
export default function HomePage() {
  return (
    <section className="home-intro">
      <BrandLogo />
      <span className="eyebrow">PERSONAL STYLE. CONSIDERED FIT.</span>
      <h1>
        See the look.
        <br />
        Find your fit.
      </h1>
      <p>
        Explore your wardrobe with photo-based try-on and brand-specific size
        guidance. A more personal way to choose what feels like you.
      </p>
      <div className="actions">
        <Link className="button" to="/catalog">
          Discover apparel
        </Link>
        <Link className="button secondary" to="/tryon">
          Try your own garment
        </Link>
      </div>
      <div className="home-steps">
        {[
          [
            "01",
            "Your proportions",
            "Estimate six measurements from a full-body photo, or enter your tape measurements.",
            "/measure",
          ],
          [
            "02",
            "Your brand",
            "Compare sourced size guides with transparent ranges and a clear explanation.",
            "/sizing",
          ],
          [
            "03",
            "Your new look",
            "Preview a garment on your own photo using your connected private Colab worker.",
            "/tryon",
          ],
        ].map(([n, title, copy, to]) => (
          <Link className="card" to={to} key={n}>
            <span className="eyebrow">{n}</span>
            <h2>{title}</h2>
            <p>{copy}</p>
          </Link>
        ))}
      </div>
      <p className="fine-print">
        Image measurements are estimates. Try-on is a visual preview, not a
        guarantee of physical fit. Save measurements to your private profile
        only when you choose.
      </p>
    </section>
  );
}
