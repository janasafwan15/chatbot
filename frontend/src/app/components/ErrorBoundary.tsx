// src/app/components/ErrorBoundary.tsx
import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** رسالة مخصصة تظهر عند الخطأ */
  message?: string;
  /** دالة تُنفَّذ عند الضغط على "إعادة المحاولة" */
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, errorMessage: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error?.message ?? "خطأ غير متوقع" };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // يمكن إرسال الخطأ لخدمة مراقبة هنا (Sentry مثلاً)
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  private handleReset = () => {
    this.setState({ hasError: false, errorMessage: "" });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        dir="rtl"
        className="min-h-[300px] flex items-center justify-center p-8"
      >
        <div className="max-w-md w-full bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-8 h-8 text-red-500" />
          </div>

          <h2 className="text-xl font-bold text-red-700 mb-2">
            {this.props.message ?? "حدث خطأ غير متوقع"}
          </h2>
          <p className="text-red-600 text-sm mb-6">
            يرجى إعادة المحاولة. إذا استمرت المشكلة، تواصل مع الدعم الفني.
          </p>

          {import.meta.env.DEV && (
            <details className="text-left mb-4 bg-red-100 rounded-lg p-3">
              <summary className="text-xs text-red-500 cursor-pointer select-none">
                تفاصيل الخطأ (dev فقط)
              </summary>
              <pre className="text-xs text-red-700 mt-2 whitespace-pre-wrap break-all">
                {this.state.errorMessage}
              </pre>
            </details>
          )}

          <button
            onClick={this.handleReset}
            className="inline-flex items-center gap-2 bg-red-500 hover:bg-red-600 text-white px-6 py-2.5 rounded-lg font-medium transition-colors"
          >
            <RefreshCcw className="w-4 h-4" />
            إعادة المحاولة
          </button>
        </div>
      </div>
    );
  }
}

/**
 * نسخة بسيطة للاستخدام كـ wrapper مباشر في JSX:
 * <WithErrorBoundary message="خطأ في القسم"><MyComponent /></WithErrorBoundary>
 */
export function WithErrorBoundary({
  children,
  message,
  onReset,
}: Props) {
  return (
    <ErrorBoundary message={message} onReset={onReset}>
      {children}
    </ErrorBoundary>
  );
}