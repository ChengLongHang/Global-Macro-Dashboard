import React, { useState, useEffect } from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { Plus, X } from 'lucide-react';

export default function ThemeMatrix({ 
  country, 
  theme, 
  onAddToWorkspace,
  onClose 
}) {
  const [indicators, setIndicators] = useState([]);
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [allIndicators, setAllIndicators] = useState([]);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/indicators')
      .then(res => res.json())
      .then(setAllIndicators)
      .catch(console.error);
  }, []);
  
  useEffect(() => {
    if (!theme || !country) return;
    
    const fetchThemeData = async () => {
      setLoading(true);
      try {
        const themeRes = await fetch(`http://localhost:8000/api/theme_indicators?theme=${theme}`);
        const themeIndicators = await themeRes.json();
        setIndicators(themeIndicators);
        
        const endDate = new Date();
        const startDate = new Date();
        startDate.setFullYear(startDate.getFullYear() - 3);
        
        const dataPromises = themeIndicators.map(async (seriesId) => {
          const res = await fetch(
            `http://localhost:8000/api/data?series_id=${seriesId}&start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}`
          );
          const seriesData = await res.json();
          return { [seriesId]: seriesData };
        });
        
        const results = await Promise.all(dataPromises);
        const combinedData = Object.assign({}, ...results);
        setData(combinedData);
      } catch (error) {
        console.error('Error fetching theme data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchThemeData();
  }, [theme, country]);
  
  const getIndicatorName = (id) => {
    const found = allIndicators.find(i => i.id === id);
    return found ? found.name : id;
  };
  
  if (!theme) return null;
  
  return (
    <div className="absolute top-24 right-5 w-96 max-h-[70vh] overflow-y-auto bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-4 z-10">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-white font-bold text-sm flex items-center gap-2">
          <span className="text-lg">📊</span> {theme} Matrix
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          <X size={18} />
        </button>
      </div>
      
      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <div className="space-y-3">
          {indicators.map(indicatorId => {
            const seriesData = data[indicatorId] || [];
            const latestValue = seriesData.length > 0 ? seriesData[seriesData.length - 1].value : null;
            
            return (
              <div key={indicatorId} className="bg-gray-800/30 rounded-xl p-3 border border-white/5">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="text-white text-sm font-medium">{getIndicatorName(indicatorId)}</p>
                    {latestValue && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Latest: {latestValue.toFixed(2)}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => onAddToWorkspace({
                      country: country.name,
                      indicator: getIndicatorName(indicatorId),
                      seriesId: indicatorId,
                      data: seriesData
                    })}
                    className="text-blue-400 hover:text-blue-300 transition-colors p-1"
                  >
                    <Plus size={16} />
                  </button>
                </div>
                <div className="h-12">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={seriesData.slice(-24)}>
                      <Line 
                        type="monotone" 
                        dataKey="value" 
                        stroke="#60a5fa" 
                        strokeWidth={1.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}