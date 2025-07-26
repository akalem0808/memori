import React from 'react';

function MemoryCard({ memory, onClick }) {
  // Function to determine card background color based on emotion
  const getEmotionColor = (emotion) => {
    const colors = {
      happy: 'bg-yellow-50 border-yellow-200',
      sad: 'bg-blue-50 border-blue-200',
      angry: 'bg-red-50 border-red-200',
      fearful: 'bg-purple-50 border-purple-200',
      disgust: 'bg-green-50 border-green-200',
      surprised: 'bg-orange-50 border-orange-200',
      neutral: 'bg-gray-50 border-gray-200'
    };
    
    return colors[emotion?.toLowerCase()] || 'bg-gray-50 border-gray-200';
  };
  
  // Get formatted date if timestamp exists
  const getFormattedDate = () => {
    if (!memory.timestamp) return 'Unknown date';
    
    try {
      const date = new Date(memory.timestamp);
      return date.toLocaleDateString(undefined, { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric'
      });
    } catch (e) {
      return 'Invalid date';
    }
  };
  
  // Get text content from either text or audio_text
  const getTextContent = () => {
    return memory.text || memory.audio_text || 'No content';
  };
  
  // Truncate text to a specific length
  const truncateText = (text, maxLength = 120) => {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div 
      className={`memory-card p-4 rounded-lg shadow-sm border cursor-pointer transition-transform hover:shadow-md hover:-translate-y-1 ${getEmotionColor(memory.emotion)}`}
      onClick={() => onClick(memory)}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="inline-block px-2 py-1 rounded-full text-xs font-medium capitalize" 
              style={{ backgroundColor: `rgba(0,0,0,0.05)` }}>
          {memory.emotion || 'Unknown'}
        </span>
        <span className="text-xs text-gray-500">
          {getFormattedDate()}
        </span>
      </div>
      
      <p className="text-gray-800 mb-3">
        {truncateText(getTextContent())}
      </p>
      
      {memory.topics && memory.topics.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {memory.topics.slice(0, 3).map((topic, index) => (
            <span key={index} className="inline-block px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
              {topic}
            </span>
          ))}
          {memory.topics.length > 3 && (
            <span className="inline-block px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
              +{memory.topics.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default MemoryCard;
