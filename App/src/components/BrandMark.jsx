import React from 'react';

// Glucosphere brand mark: a sphere (outer circle) enclosing a glucose ring
// (flat-top hexagon = the pyranose sugar ring), with a sensor node on the rim
// representing the CGM monitoring integration. Inherits color via currentColor.
export default function BrandMark({ className = 'w-7 h-7', strokeWidth = 1.8 }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth}
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {/* sphere */}
      <circle cx="12" cy="12" r="9" />
      {/* glucose ring (flat-top hexagon) */}
      <polygon points="17,12 14.5,16.33 9.5,16.33 7,12 9.5,7.67 14.5,7.67" />
      {/* monitoring sensor node on the sphere rim */}
      <circle cx="18.4" cy="5.6" r="1.7" fill="currentColor" stroke="none" />
    </svg>
  );
}
