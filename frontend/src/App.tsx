import { useState, useEffect, useCallback } from 'react';
import { Map } from '@/components/MapLibre';
import { SearchPanel } from '@/components/SearchPanel';
import { Header } from '@/components/Header';
import { FloorSelector } from '@/components/FloorSelector';
import { OfflineIndicator } from '@/components/OfflineIndicator';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';

function App() {
  const [selectedFloor, setSelectedFloor] = useState(1);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [destination, setDestination] = useState<string | null>(null);
  const [startingPoint, setStartingPoint] = useState<string | null>(null);
  const [_apiStatus, setApiStatus] = useState<string>('loading...');
  const isOnline = useOnlineStatus();

  // Test API on mount
  useEffect(() => {
    fetch('/api/floorplan/levels')
      .then(r => r.json())
      .then(d => setApiStatus(`API OK: ${d.levels?.length || 0} levels`))
      .catch(e => setApiStatus(`API Error: ${e.message}`));
  }, []);

  // Keyboard shortcut (Cmd+K or Ctrl+K) to open search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearchClick = useCallback(() => {
    setIsSearchOpen(true);
  }, []);

  const handleSearchResult = (featureId: string, floor: number) => {
    setDestination(featureId);
    setSelectedFloor(floor);
  };

  const handleNavigateToResult = (featureId: string, floor: number) => {
    setDestination(featureId);
    setSelectedFloor(floor);
  };

  const handleClearNavigation = () => {
    setDestination(null);
    setStartingPoint(null);
  };

  return (
    <div className="h-screen w-screen overflow-hidden relative bg-gray-100 safe-area-top">
      {/* Offline indicator */}
      {!isOnline && <OfflineIndicator />}

      {/* Header with search trigger */}
      <Header onSearchClick={handleSearchClick} />

      {/* Map */}
      <div className="absolute inset-0 pt-14 sm:pt-16" style={{ minHeight: '300px' }}>
        <Map
          floor={selectedFloor}
          destination={destination}
          startingPoint={startingPoint}
          onDestinationReached={handleClearNavigation}
          onSetDestination={(featureId) => setDestination(featureId)}
          onSetStartingPoint={(featureId) => setStartingPoint(featureId)}
        />
      </div>

      {/* Floor selector */}
      <FloorSelector
        currentFloor={selectedFloor}
        onFloorChange={setSelectedFloor}
      />

      {/* Search panel - appears as dropdown below header */}
      <SearchPanel
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onResultSelect={handleSearchResult}
        onNavigateToResult={handleNavigateToResult}
        currentFloor={selectedFloor}
      />
    </div>
  );
}

export default App;
