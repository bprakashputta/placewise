// Re-mounts on every route change, so each page's content fades in once (disabled under
// prefers-reduced-motion in globals.css).
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-up">{children}</div>;
}
