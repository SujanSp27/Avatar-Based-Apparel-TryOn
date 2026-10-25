import { Link } from "react-router-dom";
import BrandLogo from "../ui/BrandLogo";
export default function HomePage() {
  return (
    <section className="home-intro">
      <div className="editorial-hero">
        <div className="editorial-copy">
          <BrandLogo />
          <span className="eyebrow">STYLE, WITH A PERSONAL PERSPECTIVE</span>
          <h1>
            Your Style.
            <br />
            Your Fit.
            <br />
            <em>Your Confidence.</em>
          </h1>
          <p>
            Discover new styles, explore brand-specific size recommendations,
            and preview outfits with personalized virtual try-on.
          </p>
          <div className="actions">
            <Link className="button" to="/catalog">
              Explore Collection
            </Link>
            <Link className="button secondary" to="/tryon">
              Try Your Own Outfit
            </Link>
          </div>
          <p className="hero-feature-line">
            Virtual Try-On · Personalized Fit · Brand-Specific Sizing
          </p>
        </div>
        <figure className="editorial-photo">
          <img
            src="/editorial/beige-dress-1200.webp"
            srcSet="/editorial/beige-dress-640.webp 640w, /editorial/beige-dress-1200.webp 1200w"
            sizes="(max-width: 760px) 90vw, 40vw"
            width="1200"
            height="1996"
            fetchPriority="high"
            alt="Full-length editorial portrait in a belted beige dress"
          />
          <figcaption>
            Style inspiration ·{" "}
            <a
              href="https://www.pexels.com/photo/a-woman-wearing-a-beige-dress-13816068/"
              target="_blank"
              rel="noreferrer"
            >
              rehman yousaf / Pexels
            </a>
            <br />
            Editorial photograph, not a try-on result.
          </figcaption>
        </figure>
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
