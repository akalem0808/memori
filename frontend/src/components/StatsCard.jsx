import React from 'react';

function StatsCard({ stats }) {
  // Default values for stats
  const {
    totalMemories = 0,
    topEmotion = 'N/A',
    topTopic = 'N/A',
    avgImportance = 0,
    lastUpload = null,
    recentEmotions = []
  } = stats;
  
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return 'Invalid date';
    }
  };
  
  // Color for emotion visualization
  const getEmotionColor = (emotion) => {
    const colors = {
      happy: '#FCD34D',
      sad: '#60A5FA',
      angry: '#F87171',
      fearful: '#A78BFA',
      disgust: '#6EE7B7',
      surprised: '#FBBF24',
      neutral: '#D1D5DB'
    };
    
    return colors[emotion?.toLowerCase()] || '#D1D5DB';
  };

  return (
    <div className="stats-card bg-white p-4 rounded-lg shadow-sm h-full">
      <h3 className="text-lg font-medium mb-4">Memory Statistics</h3>
      
      <div className="grid grid-cols-2 gap-4">
        {/* Total Memories */}
        <div className="stat-item">
          <div className="text-sm text-gray-500">Total Memories</div>
          <div className="text-2xl font-bold">{totalMemories}</div>
        </div>
        
        {/* Top Emotion */}
        <div className="stat-item">
          <div className="text-sm text-gray-500">Top Emotion</div>
          <div className="text-xl font-medium capitalize flex items-center">
            <span 
              className="inline-block w-3 h-3 rounded-full mr-2" 
              style={{ backgroundColor: getEmotionColor(topEmotion) }}
            ></span>
            {topEmotion}
          </div>
        </div>
        
        {/* Top Topic */}
        <div className="stat-item">
          <div className="text-sm text-gray-500">Top Topic</div>
          <div className="text-lg font-medium">{topTopic}</div>
        </div>
        
        {/* Average Importance */}
        <div className="stat-item">
          <div className="text-sm text-gray-500">Avg Importance</div>
          <div className="text-lg font-medium">
            {Math.round(avgImportance * 100)}%
          </div>
        </div>
      </div>
      
      {/* Last Upload */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <div className="text-sm text-gray-500">Last Upload</div>
        <div className="text-md">{formatDate(lastUpload)}</div>
      </div>
      
      {/* Recent Emotions */}
      {recentEmotions && recentEmotions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="text-sm text-gray-500 mb-2">Recent Emotions</div>
          <div className="flex flex-wrap gap-1">
            {recentEmotions.map((emotion, index) => (
              <span 
                key={index}
                className="inline-block px-2 py-1 rounded-full text-xs capitalize"
                style={{ 
                  backgroundColor: getEmotionColor(emotion),
                  color: '#1F2937',
                  opacity: 0.8
                }}
              >
                {emotion}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default StatsCard;
