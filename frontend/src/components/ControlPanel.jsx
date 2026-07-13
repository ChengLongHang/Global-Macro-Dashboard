import React, { useState, useEffect } from 'react';
import { Plus, ChevronDown, ChevronUp } from 'lucide-react';

export default function ControlPanel({ 
  selectedCountry, 
  onAddToWorkspace,
  onThemeSelect,
  selectedTheme 
}) {
  const [indicators, setIndicators] = useState([]);
  const [selectedIndicator, setSelectedIndicator] = useState('');
  const [timeHorizon, setTimeHorizon] = useState(5);
  const [isExpanded, setIsExpanded] = useState(true);
  const [loading, setLoading] = useState(false);
  
  const themes = ['Labor Data', 'Interest Rates', 'Stock Market', 'Inflation', 'Economic Growth', 'Housing', 'Exchange Rates'];
  
  useEffect(() => {
    fetch('http://localhost:8000/api/indicators')
      .then(res => res.json())
      .then(setIndicators)
      .catch(console.error);
  }, []);
  
  const handleAddToWorkspace = async () => {
    if (!selectedIndicator || !selectedCountry) return;
    
    setLoading(true);
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setFullYear(startDate.getFullYear() - timeHorizon);
      
      const response = await fetch(
        `http://localhost:8000/api/data?series_id=${selectedIndicator}&start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}`
      );
      
      // Check if response is OK
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to fetch data');
      }
      
      const data = await response.json();
      
      // Check if data is empty
      if (!data || data.length === 0) {
        throw new Error('No data available for this indicator');
      }
      
      onAddToWorkspace({
        country: selectedCountry.name,
        indicator: indicators.find(i => i.id === selectedIndicator)?.name || selectedIndicator,
        seriesId: selectedIndicator,
        data: data
      });
      
      setSelectedIndicator('');
    } catch (error) {
      console.error('Error fetching data:', error);
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  if (!selectedCountry) {
    return (
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md px-8 py-4 rounded-2xl border border-white/10">
        <p className="text-gray-300 text-sm font-light tracking-wider">
          🌍 Click on any country to begin
        </p>
      </div>
    );
  }
  
  return (
    <div className="absolute top-5 left-5 max-w-sm w-full z-10">
      <div className="bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b border-white/5">
          <div>
            <h2 className="text-white font-bold text-lg flex items-center gap-2">
              <span className="text-2xl">🌍</span>
              {selectedCountry.name}
            </h2>
            <p className="text-xs text-gray-400 font-light">Select indicators to analyze</p>
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-white transition-colors"
          >
            {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="p-4 space-y-4">
            <div>
              <label className="text-xs text-gray-400 font-medium uppercase tracking-wider block mb-2">
                Select Indicator
              </label>
              <select
                value={selectedIndicator}
                onChange={(e) => setSelectedIndicator(e.target.value)}
                className="w-full bg-gray-800/50 text-white rounded-lg px-3 py-2.5 text-sm border border-white/10 focus:border-blue-500 focus:outline-none transition-colors"
              >
                <option value="">Choose an indicator...</option>
                {indicators.map(ind => (
                  <option key={ind.id} value={ind.id}>
                    {ind.name} ({ind.category})
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                <span>Time Horizon</span>
                <span>{timeHorizon} years</span>
              </div>
              <input
                type="range"
                min="1"
                max="20"
                value={timeHorizon}
                onChange={(e) => setTimeHorizon(parseInt(e.target.value))}
                className="w-full h-1.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            
            <div>
              <label className="text-xs text-gray-400 font-medium uppercase tracking-wider block mb-2">
                Quick Theme Matrix
              </label>
              <div className="flex flex-wrap gap-2">
                {themes.map(theme => (
                  <button
                    key={theme}
                    onClick={() => onThemeSelect(theme === selectedTheme ? null : theme)}
                    className={`text-xs px-3 py-1.5 rounded-full transition-all ${
                      theme === selectedTheme
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800/50 text-gray-300 hover:bg-gray-700/50'
                    }`}
                  >
                    {theme}
                  </button>
                ))}
              </div>
            </div>
            
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleAddToWorkspace}
                disabled={!selectedIndicator || loading}
                className={`flex-1 flex items-center justify-center gap-2 text-sm font-medium py-2.5 rounded-lg transition-all ${
                  !selectedIndicator || loading
                    ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20'
                }`}
              >
                <Plus size={16} />
                {loading ? 'Loading...' : 'Add to Workspace'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}