import { Search, Moon, Sun, Compass } from 'lucide-react';
import { useTheme } from '@/providers/ThemeProvider';

interface HeaderProps {
  onSearchClick: () => void;
}

export function Header({ onSearchClick }: HeaderProps) {
  const { setTheme, resolvedTheme } = useTheme();

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-r from-white/90 via-white/80 to-white/90 dark:from-dark-900/90 dark:via-dark-900/80 dark:to-dark-900/90 backdrop-blur-xl border-b border-gray-200/50 dark:border-dark-700/50 shadow-sm safe-area-top">
      <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-5 h-14 sm:h-16">
        {/* Logo/Title */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="relative">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-primary-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-primary-500/25">
              <Compass className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 rounded-full border-2 border-white dark:border-dark-900 animate-pulse" />
          </div>
          <h1 className="text-sm sm:text-base font-bold bg-gradient-to-r from-gray-900 to-gray-700 dark:from-white dark:to-gray-200 bg-clip-text text-transparent hidden sm:block">
            Navigator
          </h1>
        </div>

        {/* Search trigger button - styled like an input */}
        <button
          onClick={onSearchClick}
          className="flex-1 max-w-xl flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl border border-gray-200/80 dark:border-dark-600/80 bg-white/80 dark:bg-dark-800/80 hover:bg-white dark:hover:bg-dark-800 hover:border-gray-300 dark:hover:border-dark-500 transition-all duration-200 group"
        >
          <Search className="w-4 h-4 text-gray-400 group-hover:text-primary-500 transition-colors" />
          <span className="text-sm text-gray-400 dark:text-gray-500 truncate">
            Search people, rooms, or 'meet CEO'...
          </span>
          <kbd className="hidden md:flex items-center gap-0.5 px-1.5 py-0.5 text-xs text-gray-400 bg-gray-100 dark:bg-dark-700 rounded border border-gray-200 dark:border-dark-600">
            <span className="text-xs">⌘</span>K
          </kbd>
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 sm:p-2.5 rounded-xl bg-gray-100/80 dark:bg-dark-700/80 hover:bg-gray-200/80 dark:hover:bg-dark-600/80 transition-all duration-200 hover:scale-105 active:scale-95 flex-shrink-0"
          aria-label="Toggle theme"
        >
          {resolvedTheme === 'dark' ? (
            <Sun className="w-5 h-5 text-amber-400" />
          ) : (
            <Moon className="w-5 h-5 text-indigo-600" />
          )}
        </button>
      </div>
    </header>
  );
}
