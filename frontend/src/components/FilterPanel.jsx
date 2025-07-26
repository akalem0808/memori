import React, { useState, useEffect } from 'react';
import { getAvailableFilters } from '../services/api';

function FilterPanel({ filters, setFilters, onFilterChange }) {
  const [availableFilters, setAvailableFilters] = useState({
    emotions: [],
    topics: [],
    dateRanges: [
      { id: 'today', label: 'Today' },
      { id: 'week', label: 'This Week' },
      { id: 'month', label: 'This Month' },
      { id: 'year', label: 'This Year' },
      { id: 'all', label: 'All Time' }
    ]
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadFilters() {
      try {
        setLoading(true);
        setError(null);
        const data = await getAvailableFilters();
        setAvailableFilters(prev => ({
          ...prev,
          emotions: data.emotions || [],
          topics: data.topics || []
        }));
      } catch (err) {
        console.error('Failed to load filters:', err);
        setError('Failed to load filter options');
      } finally {
        setLoading(false);
      }
    }

    loadFilters();
  }, []);

  const handleFilterChange = (filterType, value) => {
    const newFilters = { ...filters, [filterType]: value };
    setFilters(newFilters);
    if (onFilterChange) {
      onFilterChange(newFilters);
    }
  };

  const resetFilters = () => {
    setFilters({});
    if (onFilterChange) {
      onFilterChange({});
    }
  };

  return (
    <div className="filter-panel p-4 bg-gray-50 rounded-lg shadow-sm mb-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium">Memory Filters</h3>
        <button 
          onClick={resetFilters}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Reset All
        </button>
      </div>

      {loading && <p className="text-gray-500">Loading filters...</p>}
      {error && <p className="text-red-500">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Emotion Filter */}
        <div className="filter-group">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Emotion
          </label>
          <select
            value={filters.emotion || ''}
            onChange={(e) => handleFilterChange('emotion', e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md"
          >
            <option value="">All Emotions</option>
            {availableFilters.emotions.map(emotion => (
              <option key={emotion} value={emotion}>
                {emotion.charAt(0).toUpperCase() + emotion.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Topic Filter */}
        <div className="filter-group">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Topic
          </label>
          <select
            value={filters.topic || ''}
            onChange={(e) => handleFilterChange('topic', e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md"
          >
            <option value="">All Topics</option>
            {availableFilters.topics.map(topic => (
              <option key={topic} value={topic}>{topic}</option>
            ))}
          </select>
        </div>

        {/* Date Range Filter */}
        <div className="filter-group">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Time Period
          </label>
          <select
            value={filters.dateRange || ''}
            onChange={(e) => handleFilterChange('dateRange', e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md"
          >
            <option value="">All Time</option>
            {availableFilters.dateRanges.map(range => (
              <option key={range.id} value={range.id}>{range.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Search */}
      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Search
        </label>
        <input
          type="text"
          value={filters.search || ''}
          onChange={(e) => handleFilterChange('search', e.target.value)}
          placeholder="Search memories..."
          className="w-full p-2 border border-gray-300 rounded-md"
        />
      </div>
    </div>
  );
}

export default FilterPanel;
