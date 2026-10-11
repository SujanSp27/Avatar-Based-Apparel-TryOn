// Lucide 0.511 ships per-icon ESM files but a single shared type declaration.
declare module "lucide-react/dist/esm/icons/*.js" {
  import type { LucideIcon } from "lucide-react";
  const Icon: LucideIcon;
  export default Icon;
}
