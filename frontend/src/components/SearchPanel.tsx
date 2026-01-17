import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Search,
  X,
  User,
  Building2,
  Loader2,
  MapPin,
  Sparkles,
  Route,
  Navigation,
} from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { search, type SearchResult } from '@/services/api';

interface SearchPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onResultSelect: (featureId: string, floor: number) => void;
  onNavigateToResult?: (featureId: string, floor: number) => void;
  currentFloor?: number;
}

export function SearchPanel({
  isOpen,
  onClose,
  onResultSelect,
  onNavigateToResult,
}: SearchPanelProps) {
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const searchMutation = useMutation({
    mutationFn: (query: string) => search(query),
  });

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      // Small delay to ensure the panel is visible
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Reset state when panel closes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setHasSearched(false);
      searchMutation.reset();
    }
  }, [isOpen]);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      // Delay adding the listener to prevent immediate close
      setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 100);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  const executeSearch = useCallback(() => {
    if (query.trim().length >= 2) {
      searchMutation.mutate(query.trim());
      setHasSearched(true);
    }
  }, [query, searchMutation]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeSearch();
    }
  };

  const handleResultClick = (result: SearchResult) => {
    if (result.feature_id) {
      onResultSelect(result.feature_id, result.floor);
      onClose();
    }
  };

  const handleNavigateClick = (result: SearchResult) => {
    if (result.feature_id && onNavigateToResult) {
      onNavigateToResult(result.feature_id, result.floor);
      onClose();
    }
  };

  const handleSuggestionClick = (text: string) => {
    setQuery(text);
    searchMutation.mutate(text);
    setHasSearched(true);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-30 animate-fade-in" />

      {/* Search Panel - Fixed below header */}
      <div
        ref={panelRef}
        className="fixed top-14 sm:top-16 left-0 right-0 z-40 px-3 sm:px-4 md:px-6"
      >
        <div className="max-w-2xl mx-auto bg-white dark:bg-dark-800 rounded-2xl shadow-2xl border border-gray-200/50 dark:border-dark-700/50 overflow-hidden animate-slide-down">
          {/* Search Input */}
          <div className="p-3 sm:p-4 border-b border-gray-100 dark:border-dark-700">
            <div className="relative flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setHasSearched(false);
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Search people, rooms, or 'meet CEO'..."
                  className="w-full pl-10 sm:pl-12 pr-10 py-3 text-base sm:text-lg bg-gray-50 dark:bg-dark-700 border border-gray-200 dark:border-dark-600 rounded-xl text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all"
                  style={{ fontSize: '16px' }}
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                />
                {query && (
                  <button
                    onClick={() => {
                      setQuery('');
                      setHasSearched(false);
                      searchMutation.reset();
                    }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-dark-600 transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </button>
                )}
              </div>
              <button
                onClick={executeSearch}
                disabled={query.trim().length < 2 || searchMutation.isPending}
                className="px-4 sm:px-5 py-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 font-medium"
              >
                {searchMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span className="hidden sm:inline">Search</span>
                  </>
                )}
              </button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-400">
                Press Enter or click Search
              </p>
              <button
                onClick={onClose}
                className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                Press ESC to close
              </button>
            </div>
          </div>

          {/* Results Area */}
          <div className="max-h-[60vh] sm:max-h-[50vh] overflow-y-auto">
            {/* Loading state */}
            {searchMutation.isPending && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-primary-600 animate-spin" />
                <span className="ml-3 text-gray-500 dark:text-gray-400">
                  Searching...
                </span>
              </div>
            )}

            {/* AI Intent indicator */}
            {!searchMutation.isPending && searchMutation.data?.intent && searchMutation.data.intent.confidence > 0.5 && (
              <div className="mx-4 mt-4 p-3 bg-gradient-to-r from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/20 rounded-xl border border-primary-100 dark:border-primary-800">
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary-700 dark:text-primary-300">
                      AI Understanding
                    </p>
                    <p className="text-sm text-primary-600 dark:text-primary-400 mt-0.5">
                      {searchMutation.data.intent.additional_context ||
                        `Looking for ${searchMutation.data.intent.target_category || searchMutation.data.intent.target_name || 'matching results'}`}
                    </p>
                    {searchMutation.data.intent.intent_type === 'get_directions' && (
                      <p className="text-xs text-primary-500 mt-1 flex items-center gap-1">
                        <Route className="w-3 h-3" />
                        Navigation intent detected - click Navigate on any result
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Results list */}
            {!searchMutation.isPending && searchMutation.data?.results && searchMutation.data.results.length > 0 && (
              <div className="p-3 sm:p-4 space-y-2">
                {searchMutation.data.results.map((result) => (
                  <SearchResultCard
                    key={`${result.type}-${result.id}`}
                    result={result}
                    onClick={() => handleResultClick(result)}
                    onNavigate={onNavigateToResult ? () => handleNavigateClick(result) : undefined}
                    showNavigation={
                      searchMutation.data?.intent?.intent_type === 'get_directions' ||
                      searchMutation.data?.intent?.intent_type === 'find_person'
                    }
                  />
                ))}
              </div>
            )}

            {/* No results */}
            {!searchMutation.isPending && hasSearched && searchMutation.data?.results?.length === 0 && (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-dark-700 flex items-center justify-center">
                  <Search className="w-8 h-8 text-gray-400" />
                </div>
                <p className="text-gray-600 dark:text-gray-300 font-medium">
                  No results found
                </p>
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                  Try searching for a person, room, or service
                </p>
              </div>
            )}

            {/* Suggestions - shown when no query */}
            {!searchMutation.isPending && !hasSearched && !query && (
              <div className="p-4">
                <p className="text-sm text-gray-500 dark:text-gray-400 font-medium mb-3">
                  Try searching for:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {[
                    { text: 'Need to meet CEO', icon: <User className="w-4 h-4" /> },
                    { text: 'Conference Room', icon: <Building2 className="w-4 h-4" /> },
                    { text: 'Navigate to break room', icon: <Route className="w-4 h-4" /> },
                    { text: 'Where is the restroom?', icon: <MapPin className="w-4 h-4" /> },
                    { text: 'Find Alice Johnson', icon: <User className="w-4 h-4" /> },
                    { text: 'Show me huddle rooms', icon: <Navigation className="w-4 h-4" /> },
                  ].map((suggestion) => (
                    <button
                      key={suggestion.text}
                      onClick={() => handleSuggestionClick(suggestion.text)}
                      className="text-left p-3 rounded-xl bg-gray-50 dark:bg-dark-700 hover:bg-gray-100 dark:hover:bg-dark-600 text-gray-700 dark:text-gray-300 text-sm transition-colors flex items-center gap-3"
                    >
                      <span className="text-gray-400 flex-shrink-0">{suggestion.icon}</span>
                      <span className="truncate">"{suggestion.text}"</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function SearchResultCard({
  result,
  onClick,
  onNavigate,
  showNavigation = false,
}: {
  result: SearchResult;
  onClick: () => void;
  onNavigate?: () => void;
  showNavigation?: boolean;
}) {
  const isEmployee = result.type === 'employee';

  return (
    <div className="w-full bg-gray-50 dark:bg-dark-700/50 rounded-xl p-3 sm:p-4 hover:bg-gray-100 dark:hover:bg-dark-700 transition-colors">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={`p-2 rounded-lg flex-shrink-0 ${
            isEmployee
              ? 'bg-blue-100 dark:bg-blue-900/30'
              : 'bg-emerald-100 dark:bg-emerald-900/30'
          }`}
        >
          {isEmployee ? (
            <User className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          ) : (
            <Building2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          )}
        </div>

        {/* Content */}
        <button onClick={onClick} className="flex-1 min-w-0 text-left">
          <h3 className="font-medium text-gray-900 dark:text-white truncate">
            {isEmployee ? result.name : result.display_name || result.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
            {isEmployee
              ? `${result.department || 'Employee'} • ${result.title || ''}`
              : `${result.category || 'Room'}${result.capacity ? ` • Capacity: ${result.capacity}` : ''}`}
          </p>
          {isEmployee && result.desk_id && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Desk: {result.desk_id}
            </p>
          )}
        </button>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Floor badge */}
          <div className="flex items-center gap-1 px-2 py-1 bg-white dark:bg-dark-600 rounded-lg border border-gray-200 dark:border-dark-500">
            <MapPin className="w-3 h-3 text-gray-500" />
            <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
              F{result.floor}
            </span>
          </div>

          {/* Navigate button */}
          {onNavigate && result.feature_id && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onNavigate();
              }}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition-colors ${
                showNavigation
                  ? 'bg-primary-600 text-white hover:bg-primary-700'
                  : 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-900/50'
              }`}
              title="Navigate to this location"
            >
              <Route className="w-4 h-4" />
              <span className="text-xs font-medium hidden sm:inline">Navigate</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
