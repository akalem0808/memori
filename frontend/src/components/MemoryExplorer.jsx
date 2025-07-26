import React, { useState, useEffect, useCallback } from 'react';
import MemoryCard from './MemoryCard';
import MemoryModal from './MemoryModal';
import FilterPanel from './FilterPanel';
import StatsCard from './StatsCard';
import UploadPanel from './UploadPanel';
import { fetchMemories, getMemoryStats } from '../services/api';

function MemoryExplorer() {
  // State management
  const [memories, setMemories] = useState([]);
  const [selectedMemory, setSelectedMemory] = useState(null);
  const [filters, setFilters] = useState({});
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load memories from API
  const loadMemories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchMemories(filters);
      setMemories(data);
    } catch (err) {
      console.error('Failed to load memories:', err);
      setError('Failed to load memories. Please try again later.');
      // Fallback to demo data in case of error
      setMemories([
        { id: '1', emotion: 'happy', audio_text: 'This is a happy memory.' },
        { id: '2', emotion: 'sad', audio_text: 'This is a sad memory.' },
      ]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // Load memory stats
  const loadStats = useCallback(async () => {
    try {
      const statsData = await getMemoryStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load memory stats:', err);
      // Set default stats on error
      setStats({
        totalMemories: memories.length,
        topEmotion: 'unknown',
        avgImportance: 0
      });
    }
  }, [memories.length]);

  // Initial data loading
  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  // Handle successful upload
  const handleUploadComplete = useCallback((newMemory) => {
    // Refresh memories list
    loadMemories();
    // Refresh stats
    loadStats();
  }, [loadMemories, loadStats]);

  return (
    <div className="memory-explorer p-4 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Memory Explorer</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2">
          <UploadPanel onUploadComplete={handleUploadComplete} />
        </div>
        <div>
          <StatsCard stats={stats} />
        </div>
      </div>
      
      <FilterPanel 
        filters={filters} 
        setFilters={setFilters} 
        onFilterChange={handleFilterChange} 
      />
      
      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
        </div>
      )}
      
      {/* Error State */}
      {error && (
        <div className="text-red-500 bg-red-50 p-4 rounded-md mb-4">
          {error}
        </div>
      )}
      
      {/* No Results */}
      {!loading && !error && memories.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-md">
          <h3 className="text-xl font-medium text-gray-600 mb-2">No memories found</h3>
          <p className="text-gray-500">Try changing your filters or upload a new memory.</p>
        </div>
      )}
      
      {/* Memory Grid */}
      {!loading && memories.length > 0 && (
        <div className="memory-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {memories.map(memory => (
            <MemoryCard 
              key={memory.id} 
              memory={memory} 
              onClick={() => setSelectedMemory(memory)} 
            />
          ))}
        </div>
      )}
      
      {/* Memory Detail Modal */}
      {selectedMemory && (
        <MemoryModal 
          memory={selectedMemory} 
          onClose={() => setSelectedMemory(null)} 
        />
      )}
    </div>
  );
}

export default MemoryExplorer;
