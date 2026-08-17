import { useEffect, useState } from "react";

/** Floating scroll-to-top / scroll-to-bottom buttons, shown once the page
 * has enough content to make them useful. Mounted once per page/view
 * (App.jsx renders it inside every top-level branch) so it appears
 * everywhere, not just on the Studio screens. */
function ScrollToTopBottom() {
  const [showTop, setShowTop] = useState(false);
  const [showBottom, setShowBottom] = useState(false);

  useEffect(() => {
    const update = () => {
      const scrollY = window.scrollY;
      const viewportHeight = window.innerHeight;
      const pageHeight = document.documentElement.scrollHeight;
      setShowTop(scrollY > 300);
      setShowBottom(scrollY + viewportHeight < pageHeight - 300);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  if (!showTop && !showBottom) return null;

  return (
    <div className="scroll-fab-stack">
      {showTop && (
        <button
          type="button"
          className="scroll-fab"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Scroll to top"
          title="Scroll to top"
        >
          ↑
        </button>
      )}
      {showBottom && (
        <button
          type="button"
          className="scroll-fab"
          onClick={() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" })}
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
        >
          ↓
        </button>
      )}
    </div>
  );
}

export default ScrollToTopBottom;
