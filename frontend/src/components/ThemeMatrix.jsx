import React, { useState, useEffect } from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { Plus, X } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function ThemeMatrix({ 
  country, 
  theme, 
  onAddToWorkspace,
  onClose 
}) {
  const [indicators, setIndicators] = useState([]);
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    if (!theme || !country) return;
    
    const fetchThemeData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch theme indicators for this country
        const themeRes = await fetch(`${API_BASE_URL}/api/theme_indicators/${country.id}?theme=${theme}`);
        if (!themeRes.ok) {
          throw new Error('Failed to fetch theme indicators');
        }
        const themeIndicators = await themeRes.json();
        setIndicators(themeIndicators);
        
        // Fetch data for each indicator
        const endDate = new Date();
        const startDate = new Date();
        startDate.setFullYear(startDate.getFullYear() - 3);
        
        const dataPromises = themeIndicators.map(async (indicator) => {
          const res = await fetch(
            `${API_BASE_URL}/api/data?series_id=${indicator.id}&country_id=${country.id}&start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}`
          );
          if (!res.ok) {
            return { [indicator.id]: [] };
          }
          const seriesData = await res.json();
          return { [indicator.id]: seriesData };
        });
        
        const results = await Promise.all(dataPromises);
        const combinedData = Object.assign({}, ...results);
        setData(combinedData);
      } catch (error) {
        console.error('Error fetching theme data:', error);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchThemeData();
  }, [theme, country]);
  
  if (!theme) return null;
  
  return (
    <div className="absolute top-24 right-5 w-96 max-h-[70vh] overflow-y-auto bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-4 z-10">
      <div className="flex justify-between items-center mb-4 sticky top-0 bg-black/70 backdrop-blur-xl">
        <h3 className="text-white font-bold text-sm flex items-center gap-2">
          <span className="text-lg">📊</span> {theme} Matrix - {country.name}
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          <X size={18} />
        </button>
      </div>
      
      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="text-red-400 text-sm p-4 text-center">
          Error: {error}
        </div>
      ) : indicators.length === 0 ? (
        <div className="text-gray-400 text-sm p-4 text-center">
          No indicators available for this theme in {country.name}
        </div>
      ) : (
        <div className="space-y-3">
          {indicators.map(indicator => {
            const seriesData = data[indicator.id] || [];
            const latestValue = seriesData.length > 0 ? seriesData[seriesData.length - 1].value : null;
            
            return (
              <div key={indicator.id} className="bg-gray-800/30 rounded-xl p-3 border border-white/5">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="text-white text-sm font-medium">{indicator.name}</p>
                    <p className="text-xs text-gray-500">Source: {indicator.source}</p>
                    {latestValue && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Latest: {latestValue.toFixed(2)}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      if (seriesData.length > 0) {
                        onAddToWorkspace({
                          country: country.name,
                          countryId: country.id,
                          indicator: indicator.name,
                          seriesId: indicator.id,
                          source: indicator.source,
                          data: seriesData
                        });
                      }
                    }}
                    disabled={seriesData.length === 0}
                    className={`p-1 rounded transition-colors ${
                      seriesData.length === 0
                        ? 'text-gray-600 cursor-not-allowed'
                        : 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                    }`}
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
