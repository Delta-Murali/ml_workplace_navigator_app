import { WifiOff } from 'lucide-react';

export function OfflineIndicator() {
  return (
    <div className="fixed top-16 left-0 right-0 z-50 bg-amber-500 text-white px-4 py-2">
      <div className="flex items-center justify-center gap-2">
        <WifiOff className="w-4 h-4" />
        <span className="text-sm font-medium">
          You're offline. Some features may be unavailable.
        </span>
      </div>
    </div>
  );
}
