import React from 'react';

// Glucosphere brand mark: the glucose pyranose ring (the six-membered sugar
// ring that is the molecule a CGM measures) drawn Haworth-style with a CH2OH
// branch + OH stubs, plus a live-reading sensor node. No enclosing circle, so
// it reads as a unique glucose-monitoring mark rather than a target/button.
// Inherits color via currentColor.
export default function BrandMark({ className = 'w-7 h-7' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {/* pyranose sugar ring */}
      <polygon points="17,11 14,16 8,16 5.5,11 8,6 14,6" />
      {/* CH2OH branch + OH stubs */}
      <path d="M8 6 L8 2.6" />
      <path d="M17 11 L20.4 11" />
      <path d="M8 16 L8 19.4" />
      {/* live-reading sensor node */}
      <circle cx="14" cy="6" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}
