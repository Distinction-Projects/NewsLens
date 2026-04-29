const DEFAULT_SITE_URL = "http://localhost:3000";

export function publicSiteUrl() {
  const configured =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_APP_URL ||
    process.env.SITE_URL ||
    process.env.APP_URL ||
    process.env.BASE_URL;
  return (configured || DEFAULT_SITE_URL).replace(/\/+$/, "");
}
