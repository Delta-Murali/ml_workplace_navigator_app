import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, X, Loader2, MapPin, User, Navigation, Route, Sparkles, Building2 } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { search, type SearchResult } from '@/services/api';

interface SearchDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onResultSelect: (featureId: string, floor: number) => void;
  onNavigateToResult?: (featureId: string, floor: number) => void;
  currentFloor: number;
  initialQuery?: string;
  onQueryChange?: (query: string) => void;
}

export function SearchDrawer({
  isOpen,
  onClose,
  onResultSelect,
  onNavigateToResult,
  currentFloor,
  initialQuery = '',
  onQueryChange,
}: SearchDrawerProps) {
  const [query, setQuery] = useState(initialQuery);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync query with initialQuery from parent
  useEffect(() => {
    if (initialQuery && initialQuery !== query) {
      setQuery(initialQuery);
      // Auto-search if there's an initial query when drawer opens
      if (isOpen && initialQuery.trim().length >= 2) {
        searchMutation.mutate(initialQuery.trim());
        setHasSearched(true);
      }
    }
  }, [initialQuery, isOpen]);

  const searchMutation = useMutation({
    mutationFn: (q: string) => search(q, { floor: currentFloor }),
    onSuccess: () => {
      setHasSearched(true);
    },
  });

  // Execute search function
  const executeSearch = useCallback(() => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length >= 2) {
      searchMutation.mutate(trimmedQuery);
    }
  }, [query, searchMutation]);

  // Handle Enter key press
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeSearch();
    }
  }, [executeSearch]);

  // Handle blur (focus out)
  const handleBlur = useCallback(() => {
    // Small delay to allow clicking on suggestions
    setTimeout(() => {
      if (query.trim().length >= 2 && !hasSearched) {
        executeSearch();
      }
    }, 150);
  }, [query, hasSearched, executeSearch]);

  const handleResultClick = useCallback(
    (result: SearchResult) => {
      if (result.feature_id) {
        onResultSelect(result.feature_id, result.floor);
      }
    },
    [onResultSelect]
  );

  const handleNavigateClick = useCallback(
    (result: SearchResult) => {
      if (result.feature_id && onNavigateToResult) {
        onNavigateToResult(result.feature_id, result.floor);
        handleClose();
      }
    },
    [onNavigateToResult]
  );

  const handleClose = useCallback(() => {
    setQuery('');
    setHasSearched(false);
    onQueryChange?.('');
    onClose();
  }, [onClose, onQueryChange]);

  // Reset hasSearched when query changes and sync with parent
  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newQuery = e.target.value;
    setQuery(newQuery);
    setHasSearched(false);
    onQueryChange?.(newQuery);
  }, [onQueryChange]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-30 animate-fade-in"
        onClick={handleClose}
      />

      {/* Drawer */}
      <div className="bottom-sheet z-40 animate-slide-up max-h-[85vh] sm:max-h-[80vh] flex flex-col safe-area-bottom">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-12 h-1.5 bg-gray-300 dark:bg-dark-600 rounded-full" />
        </div>

        {/* Search input */}
        <div className="px-3 sm:px-4 pb-3">
          <div className="relative flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={handleQueryChange}
                onKeyDown={handleKeyDown}
                onBlur={handleBlur}
                placeholder="Search people, rooms, or 'meet CEO'"
                className="search-input pl-10 sm:pl-12 pr-10 w-full text-sm sm:text-base"
                autoFocus
                autoComplete="off"
                autoCorrect="off"
                spellCheck="false"
              />
              {query && (
                <button
                  onClick={() => {
                    setQuery('');
                    setHasSearched(false);
                  }}
                  className="absolute right-2 sm:right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-dark-700 touch-manipulation"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </button>
              )}
            </div>
            <button
              onClick={executeSearch}
              disabled={query.trim().length < 2 || searchMutation.isPending}
              className="px-3 sm:px-4 py-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1 sm:gap-2 touch-manipulation"
            >
              {searchMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">Search</span>
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1 ml-1">Press Enter or click Search to find results</p>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-4 pb-6 scrollbar-hide">
          {/* Loading state */}
          {searchMutation.isPending && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-primary-600 animate-spin" />
              <span className="ml-2 text-gray-500 dark:text-gray-400">
                Searching...
              </span>
            </div>
          )}

          {/* AI Intent indicator */}
          {searchMutation.data?.intent && searchMutation.data.intent.confidence > 0.5 && (
            <div className="mb-4 p-3 bg-gradient-to-r from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/20 rounded-xl border border-primary-100 dark:border-primary-800">
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
                    <p className="text-xs text-primary-500 dark:text-primary-500 mt-1 flex items-center gap-1">
                      <Route className="w-3 h-3" />
                      Navigation intent detected - click Navigate on any result
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Results list */}
          {searchMutation.data?.results && searchMutation.data.results.length > 0 && (
            <div className="space-y-2">
              {searchMutation.data.results.map((result) => (
                <SearchResultCard
                  key={`${result.type}-${result.id}`}
                  result={result}
                  onClick={() => handleResultClick(result)}
                  onNavigate={onNavigateToResult ? () => handleNavigateClick(result) : undefined}
                  showNavigation={searchMutation.data?.intent?.intent_type === 'get_directions' || searchMutation.data?.intent?.intent_type === 'find_person'}
                />
              ))}
            </div>
          )}

          {/* No results */}
          {searchMutation.data?.results && searchMutation.data.results.length === 0 && (
            <div className="text-center py-8">
              <p className="text-gray-500 dark:text-gray-400">
                No results found for "{query}"
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                Try searching for a person, room, or service
              </p>
            </div>
          )}

          {/* Empty state */}
          {!query && !hasSearched && (
            <div className="space-y-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">
                Try searching or asking:
              </p>
              <div className="space-y-2">
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
                    onClick={() => {
                      setQuery(suggestion.text);
                      // Auto-search for suggestions
                      setTimeout(() => {
                        searchMutation.mutate(suggestion.text);
                        setHasSearched(true);
                      }, 100);
                    }}
                    className="w-full text-left p-3 rounded-xl bg-gray-50 dark:bg-dark-700 hover:bg-gray-100 dark:hover:bg-dark-600 text-gray-700 dark:text-gray-300 text-sm transition-colors flex items-center gap-3"
                  >
                    <span className="text-gray-400">{suggestion.icon}</span>
                    "{suggestion.text}"
                  </button>
                ))}
              </div>
            </div>
          )}
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
    <div className="w-full card p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={`p-2 rounded-lg ${
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
        <div className="flex items-center gap-2">
          {/* Floor badge */}
          <div className="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-dark-700 rounded-lg">
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
              <span className="text-xs font-medium">Navigate</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
