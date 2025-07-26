import React, { useEffect, useRef } from 'react';

function MemoryModal({ memory, onClose }) {
  const modalRef = useRef(null);
  const backdropRef = useRef(null);
  
  // Handle escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);
  
  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === backdropRef.current) {
      onClose();
    }
  };
  
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleString(undefined, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return 'Invalid date';
    }
  };
  
  // Get main text content
  const getTextContent = () => {
    return memory.text || memory.audio_text || 'No content available';
  };
  
  if (!memory) return null;
  
  return (
    <div 
      ref={backdropRef}
      className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
      onClick={handleBackdropClick}
    >
      <div 
        ref={modalRef}
        className="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-xl"
      >
        {/* Header */}
        <div className="border-b p-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-800">Memory Details</h2>
          <button 
            onClick={onClose}
            className="text-gray-500 hover:text-gray-800 focus:outline-none"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6">
          {/* Date and Emotion */}
          <div className="mb-6 flex flex-wrap gap-4 items-center">
            <div className="bg-gray-100 px-3 py-1 rounded-full text-sm">
              <span className="font-medium">Date:</span> {formatDate(memory.timestamp)}
            </div>
            
            <div className="bg-gray-100 px-3 py-1 rounded-full text-sm capitalize">
              <span className="font-medium">Emotion:</span> {memory.emotion || 'Unknown'}
            </div>
            
            {memory.importance_score !== undefined && (
              <div className="bg-gray-100 px-3 py-1 rounded-full text-sm">
                <span className="font-medium">Importance:</span> {Math.round(memory.importance_score * 100)}%
              </div>
            )}
          </div>
          
          {/* Main Content */}
          <div className="mb-6">
            <h3 className="text-lg font-medium mb-2">Content</h3>
            <div className="bg-gray-50 p-4 rounded-md whitespace-pre-wrap">
              {getTextContent()}
            </div>
          </div>
          
          {/* Topics */}
          {memory.topics && memory.topics.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-medium mb-2">Topics</h3>
              <div className="flex flex-wrap gap-2">
                {memory.topics.map((topic, index) => (
                  <span key={index} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {/* Tags */}
          {memory.tags && memory.tags.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-medium mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {memory.tags.map((tag, index) => (
                  <span key={index} className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {/* Emotion Details */}
          {memory.emotion_scores && Object.keys(memory.emotion_scores).length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-medium mb-2">Emotion Analysis</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(memory.emotion_scores).map(([emotion, score]) => (
                  <div key={emotion} className="bg-gray-50 p-2 rounded">
                    <div className="text-sm capitalize">{emotion}</div>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                      <div 
                        className="bg-blue-600 h-2 rounded-full" 
                        style={{ width: `${Math.round(score * 100)}%` }}
                      ></div>
                    </div>
                    <div className="text-xs text-right mt-1">{Math.round(score * 100)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Metadata */}
          {memory.metadata && Object.keys(memory.metadata).length > 0 && (
            <div>
              <h3 className="text-lg font-medium mb-2">Additional Information</h3>
              <div className="bg-gray-50 p-4 rounded-md">
                <pre className="text-xs text-gray-600 overflow-auto">
                  {JSON.stringify(memory.metadata, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="border-t p-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default MemoryModal;
