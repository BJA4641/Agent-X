import Link from "next/link";
export default function Header() {
  return (
    <header className="site">
      <div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>build<b>along</b></Link>
        <nav className="top">
          <a href="/#how">How it works</a>
          <a href="/#tracks">Tracks</a>
          <a href="/proof">Case study</a>
          <Link href="/login">Sign in</Link>
          <a className="cta" href="/#waitlist">Join the waitlist</a>
        </nav>
      </div>
    </header>
  );
}
