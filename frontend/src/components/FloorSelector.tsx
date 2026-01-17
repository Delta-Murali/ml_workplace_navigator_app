import { ChevronUp, ChevronDown } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getBuildingInfo } from '@/services/api';

interface FloorSelectorProps {
  currentFloor: number;
  onFloorChange: (floor: number) => void;
}

export function FloorSelector({ currentFloor, onFloorChange }: FloorSelectorProps) {
  const { data: building } = useQuery({
    queryKey: ['building'],
    queryFn: getBuildingInfo,
  });

  const floors = building?.floors || [
    { floor_number: 1, name: 'Ground Floor', ordinal: 0 },
    { floor_number: 2, name: 'Floor 2', ordinal: 1 },
    { floor_number: 3, name: 'Floor 3', ordinal: 2 },
    { floor_number: 4, name: 'Floor 4', ordinal: 3 },
    { floor_number: 5, name: 'Floor 5', ordinal: 4 },
    { floor_number: 6, name: 'Floor 6', ordinal: 5 },
  ];

  const currentIndex = floors.findIndex((f) => f.floor_number === currentFloor);
  const canGoUp = currentIndex < floors.length - 1;
  const canGoDown = currentIndex > 0;

  const goUp = () => {
    if (canGoUp) {
      onFloorChange(floors[currentIndex + 1].floor_number);
    }
  };

  const goDown = () => {
    if (canGoDown) {
      onFloorChange(floors[currentIndex - 1].floor_number);
    }
  };

  return (
    <div className="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 z-10">
      <div className="card flex flex-col items-center shadow-lg">
        {/* Up button */}
        <button
          onClick={goUp}
          disabled={!canGoUp}
          className="p-1.5 sm:p-2 hover:bg-gray-100 dark:hover:bg-dark-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors rounded-t-xl touch-manipulation"
          aria-label="Go up one floor"
        >
          <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600 dark:text-gray-300" />
        </button>

        {/* Current floor display */}
        <div className="px-3 sm:px-4 py-1.5 sm:py-2 border-y border-gray-100 dark:border-dark-700">
          <span className="text-base sm:text-lg font-semibold text-primary-600 dark:text-primary-400">
            {currentFloor}
          </span>
        </div>

        {/* Down button */}
        <button
          onClick={goDown}
          disabled={!canGoDown}
          className="p-1.5 sm:p-2 hover:bg-gray-100 dark:hover:bg-dark-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors rounded-b-xl touch-manipulation"
          aria-label="Go down one floor"
        >
          <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600 dark:text-gray-300" />
        </button>
      </div>

      {/* Floor name tooltip - hidden on mobile */}
      <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 whitespace-nowrap hidden md:block">
        <div className="px-3 py-1.5 bg-dark-900 dark:bg-white text-white dark:text-dark-900 text-sm font-medium rounded-lg shadow-lg">
          {floors[currentIndex]?.name || `Floor ${currentFloor}`}
        </div>
      </div>
    </div>
  );
}
