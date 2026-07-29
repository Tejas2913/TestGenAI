/**
 * TestGen AI v2.2 — QualityLayout Component
 *
 * Layout container for dashboard section grid arrangement. Responsive across Desktop, Laptop, and Tablet.
 */

import React from 'react';

export interface QualityLayoutProps {
  children: React.ReactNode;
}

export const QualityLayout: React.FC<QualityLayoutProps> = ({ children }) => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
      {children}
    </div>
  );
};

export default QualityLayout;
