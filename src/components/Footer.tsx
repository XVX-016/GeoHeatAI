export function Footer() {
  return (
    <footer className="border-t border-[#1f1f1f] bg-black w-full">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10 py-6 flex flex-col md:flex-row items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wide">
        <div className="flex items-center gap-1 text-white font-semibold">
          <span>GEOHEAT</span>
          <span className="text-[#F97316]">AI</span>
          <span className="text-[#6b6b6b] font-normal ml-1">© 2026</span>
        </div>
        <nav className="flex items-center gap-3 text-[#a0a0a0]">
          <a
            href="https://github.com/XVX-016/GeoHeatAI"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            GitHub
          </a>
          <span className="text-[#3a3a3a]">|</span>
          <a
            href="https://tanmmay.me"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors"
          >
            Portfolio
          </a>
        </nav>
      </div>
    </footer>
  );
}
