export function getAuthRedirect(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\x00-\x20]/.test(value)) return "/";
  const pathname = value.split(/[?#]/, 1)[0];
  if (pathname === "/login" || pathname === "/register") return "/";
  return value;
}

export function navigateAfterAuth(value: string | null): void {
  // Discard redirects prefetched before the authentication cookie existed.
  window.location.replace(getAuthRedirect(value));
}
