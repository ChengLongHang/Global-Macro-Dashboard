import React, { useState } from 'react';
import Globe from './components/Globe';
import ControlPanel from './components/ControlPanel';
import ThemeMatrix from './components/ThemeMatrix';
import WorkspacePanel from './components/WorkspacePanel';
import { useWorkspaceStore } from './store/workspaceStore';

function App() {
  const [selectedCountry, setSelectedCountry] = useState(null);
  const [hoveredCountry, setHoveredCountry] = useState(null);
  const [selectedTheme, setSelectedTheme] = useState(null);
  const { addItem } = useWorkspaceStore();
  
  return (
    <div className="relative">
      {/* 3D Globe - Full Screen */}
      <Globe 
        onSelectCountry={setSelectedCountry}
        selectedCountry={selectedCountry}
        onHoverCountry={setHoveredCountry}
      />
      
      {/* Country name tooltip on hover */}
      {hoveredCountry && !selectedCountry && (
        <div className="absolute top-5 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md px-6 py-3 rounded-2xl border border-white/10">
          <p className="text-white font-medium">{hoveredCountry.name}</p>
        </div>
      )}
      
      {/* Control Panel (Top Left) */}
      <ControlPanel 
        selectedCountry={selectedCountry}
        onAddToWorkspace={addItem}
        onThemeSelect={setSelectedTheme}
        selectedTheme={selectedTheme}
      />
      
      {/* Theme Matrix (Top Right) */}
      {selectedTheme && selectedCountry && (
        <ThemeMatrix 
          country={selectedCountry}
          theme={selectedTheme}
          onAddToWorkspace={addItem}
          onClose={() => setSelectedTheme(null)}
        />
      )}
      
      {/* Workspace Panel (Bottom) */}
      <WorkspacePanel />
    </div>
  );
}

export default App;