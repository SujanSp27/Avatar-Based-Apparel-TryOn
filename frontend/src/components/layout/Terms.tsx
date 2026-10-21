export default function Terms() {
  return (
    <article className="card legal-page">
      <span className="eyebrow">STUDIO NOTES · 21 OCTOBER 2026</span>
      <h1>A little clarity.</h1>
      <h2>What you’re agreeing to</h2>
      <p>
        Use FormFit Studio with photos you have permission to process. This is a
        research prototype for measurement estimates, chart matching and virtual
        outfit previews, not a guarantee that clothing will fit.
      </p>
      <h2>Your photos and measurements</h2>
      <p>
        Measurement extraction runs on this app’s CPU. Try-on images go only to
        your connected private Google Colab worker. Generated images, uploaded
        photos and diagnostics remain in local project storage until deleted.
        Legacy guest extraction and try-on asset links are accessible to people
        with the link; this installation is intended for localhost use, not
        public hosting.
      </p>
      <p>
        Saved profile scans, thumbnails and brand sizes require your signed-in
        session. You can delete them from your profile. Deleting a saved profile
        scan does not remove separate guest extraction diagnostics or try-on
        runs.
      </p>
      <h2>Your account</h2>
      <p>
        Passwords are hashed with Argon2. Short-lived access tokens are held in
        memory; a rotating HTTP-only cookie restores your session. “Remember me”
        allows up to 30 days; other refresh sessions last up to one day and use
        a browser-session cookie. Signing out revokes that session. Password
        resets require configured email delivery.
      </p>
      <h2>Understanding the results</h2>
      <p>
        Single-photo body dimensions depend on height, perspective, clothes and
        pose. In particular, hip joint spacing is not outer hip circumference.
        Correct estimates using a tape measure. Fit confidence is a mathematical
        chart-similarity score, not a calibrated probability. Official brand
        charts may be product-specific; fictional demo charts are labelled.
      </p>
      <h2>Before public deployment</h2>
      <p>
        This installation does not yet provide enterprise SSO, multi-factor
        authentication or verified email ownership. Configure HTTPS, secure
        cookies, a private signing secret, SMTP, access isolation for legacy
        assets, a retention policy and your organization’s legal/privacy terms
        before offering a public service.
      </p>
    </article>
  );
}
