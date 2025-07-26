// Root React component
import React from 'react';
import MemoryExplorer from './components/MemoryExplorer';

function App() {
  return (
    <div className="app-root min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center">
          <h1 className="text-2xl font-bold text-blue-600">Memori</h1>
          <p className="ml-4 text-gray-500">Audio Memory System</p>
        </div>
      </header>
      
      <main className="max-w-6xl mx-auto py-6 px-4">
        <MemoryExplorer />
      </main>
      
      <footer className="bg-white mt-12 border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 text-center text-gray-500 text-sm">
          © {new Date().getFullYear()} Memori Audio Memory System
        </div>
      </footer>
    </div>
  );
}

export default App;
