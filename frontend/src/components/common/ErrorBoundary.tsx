/**
 * TestGen AI v2.2 — ErrorBoundary Component
 *
 * Catches JavaScript rendering errors in child widget components and renders a fallback UI,
 * preventing a single failing widget from breaking the rest of the Quality Dashboard.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="rounded-xl border border-red-200 bg-red-50/50 p-4 text-left dark:border-red-900/40 dark:bg-red-950/20">
          <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h4 className="text-xs font-semibold uppercase tracking-wider">
              {this.props.fallbackTitle || 'Widget Unavailable'}
            </h4>
          </div>
          <p className="mt-1 text-xs text-red-600 dark:text-red-300">
            {this.state.error?.message || 'Failed to render dashboard component.'}
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
