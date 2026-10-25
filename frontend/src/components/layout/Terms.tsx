export default function Terms() {
  return (
    <article className="card legal-page">
      <span className="eyebrow">STUDIO NOTES · 21 OCTOBER 2026</span>
      <h1>A little clarity.</h1>
      <h2>What you’re agreeing to</h2>
      <p>
        Use VastraView with photos you have permission to process. This is a
        research prototype for measurement estimates, chart matching and virtual
        outfit previews, not a guarantee that clothing will fit.
      </p>
      <h2>Your photos and measurements</h2>
      <p>
        Measurement extraction runs on this app’s CPU. Try-on images go only to
        your connected private Google Colab worker. Generated images, uploaded
        photos and diagnostics remain in local project storage until deleted.
        New extraction and try-on images require their owning account or browser
        session. Legacy records without owners are withheld from public access.
      </p>
      <p>
        Saved profile scans, thumbnails and brand sizes require your signed-in
        session. You can delete them from your profile. Deleting a saved profile
        scan does not remove separate guest extraction diagnostics or try-on
        runs.
      </p>
      <p>
        Account settings let you delete completed try-on photos, results and
        your account. Default retention is 24 hours for guest processing data
        and 30 days for account-generated files. The operator must schedule the
        cleanup task; saved profile scans remain until deleted. Colab files and
        backups follow separate retention policies and require operator cleanup.
      </p>
      <h2>Your account</h2>
      <p>
        Passwords are hashed with Argon2. Short-lived access tokens are held in
        memory and a short-lived HttpOnly cookie for private images; a rotating
        refresh cookie restores your session. “Remember me” allows up to 30
        days; other refresh sessions last up to one day and use a
        browser-session cookie. Signing out revokes that session. Password
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
        Production configuration requires email verification, HTTPS, secure
        cookies, a private signing secret and SMTP. Verify real delivery,
        deployment security, backups and retention scheduling before public use.
        Supply your organization’s contact details and reviewed legal/privacy
        terms. Colab is temporary infrastructure without an availability
        guarantee.
      </p>
      <h2>Catalog references</h2>
      <p>
        Brand names do not imply official partnerships. Research reference
        images are labelled and excluded from production until usage rights are
        documented. Size charts retain their source, market and audience;
        missing dimensions are never fabricated.
      </p>
    </article>
  );
}
