export default function BrandLogo({ compact = false }: { compact?: boolean }) {
  return (
    <img
      className={compact ? "brand-logo compact" : "brand-logo"}
      src="/brand/vastraview.jpeg"
      alt="VastraView"
      width="1600"
      height="597"
      decoding="async"
    />
  );
}
