import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useWorkspaceStore } from '../store/workspaceStore';
import { Trash2, X, Maximize2, Minimize2, Download } from 'lucide-react';

export default function WorkspacePanel() {
  const { items, removeItem, clearAll } = useWorkspaceStore();
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Filter out items with invalid data
  const validItems = items.filter(item => {
    if (!item.data) {
      console.warn('Item missing data:', item);
      return false;
    }
    if (!Array.isArray(item.data)) {
      console.warn('Item data is not an array:', item);
      return false;
    }
    if (item.data.length === 0) {
      console.warn('Item has empty data:', item);
      return false;
    }
    return true;
  });
  
  // Show empty state
  if (items.length === 0) {
    return (
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md px-8 py-4 rounded-2xl border border-white/10 z-10">
        <p className="text-gray-400 text-sm font-light tracking-wider">
          📊 Add indicators to workspace to compare them
        </p>
      </div>
    );
  }
  
  // Show warning if no valid data
  if (validItems.length === 0) {
    return (
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md px-8 py-4 rounded-2xl border border-white/10 z-10">
        <p className="text-yellow-400 text-sm font-light tracking-wider">
          ⚠️ No valid data in workspace. Try re-adding indicators.
        </p>
        <button
          onClick={clearAll}
          className="text-xs text-red-400 hover:text-red-300 mt-2 underline"
        >
          Clear Workspace
        </button>
      </div>
    );
  }
  
  // Combine data for overlay - SAFE version
  const allDates = new Set();
  validItems.forEach(item => {
    if (Array.isArray(item.data)) {
      item.data.forEach(d => {
        if (d && d.date) {
          allDates.add(d.date);
        }
      });
    }
  });
  
  // If no dates found, show message
  if (allDates.size === 0) {
    return (
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md px-8 py-4 rounded-2xl border border-white/10 z-10">
        <p className="text-yellow-400 text-sm font-light tracking-wider">
          ⚠️ No date data available. Try re-adding indicators.
        </p>
        <button
          onClick={clearAll}
          className="text-xs text-red-400 hover:text-red-300 mt-2 underline"
        >
          Clear Workspace
        </button>
      </div>
    );
  }
  
  // Build combined data for the chart
  const combinedData = Array.from(allDates)
    .sort()
    .slice(-60) // Show last 60 data points for performance
    .map(date => {
      const point = { date };
      validItems.forEach(item => {
        if (Array.isArray(item.data)) {
          const found = item.data.find(d => d && d.date === date);
          if (found && found.value !== undefined && found.value !== null) {
            point[item.id] = found.value;
          } else {
            point[item.id] = null;
          }
        }
      });
      return point;
    });
  
  // Export data as CSV
  const exportCSV = () => {
    if (combinedData.length === 0) return;
    
    // Create headers
    let headers = 'Date';
    validItems.forEach(item => {
      headers += `,${item.country} - ${item.indicator}`;
    });
    
    // Create rows
    let csv = headers + '\n';
    combinedData.forEach(point => {
      let row = point.date;
      validItems.forEach(item => {
        const value = point[item.id];
        row += value !== null && value !== undefined ? `,${value}` : ',';
      });
      csv += row + '\n';
    });
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workspace_data_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  
  return (
    <div className={`absolute bottom-5 left-5 right-5 transition-all duration-300 z-10 ${
      isExpanded ? 'h-[60vh]' : 'h-56'
    }`}>
      <div className="bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl h-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-3 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-3">
            <h3 className="text-white font-semibold text-sm flex items-center gap-2">
              <span>📊</span> Workspace
              <span className="text-xs bg-blue-600/30 text-blue-300 px-2 py-0.5 rounded-full">
                {validItems.length}
              </span>
            </h3>
            <div className="flex flex-wrap gap-1.5 max-w-xs overflow-hidden">
              {validItems.slice(0, 3).map(item => (
                <span 
                  key={item.id}
                  className="text-[10px] px-2 py-0.5 rounded-full text-white/80 border border-white/10"
                  style={{ borderColor: item.color || '#6bcbff' }}
                >
                  {item.country || 'Unknown'}
                </span>
              ))}
              {validItems.length > 3 && (
                <span className="text-[10px] text-gray-400">+{validItems.length - 3}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Export Button */}
            <button
              onClick={exportCSV}
              className="text-gray-400 hover:text-green-400 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              title="Export data as CSV"
            >
              <Download size={16} />
            </button>
            {/* Expand/Collapse Button */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            >
              {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
            {/* Clear All Button */}
            <button
              onClick={clearAll}
              className="text-red-400 hover:text-red-300 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
        
        {/* Chart */}
        <div className="flex-1 p-3 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={combinedData}>
              <XAxis 
                dataKey="date" 
                stroke="#4a4a6a" 
                tick={{ fontSize: 10, fill: '#888' }}
                tickLine={false}
                tickFormatter={(value) => {
                  // Show fewer labels for readability
                  const date = new Date(value);
                  return `${date.getMonth()+1}/${date.getFullYear().toString().slice(-2)}`;
                }}
                interval="preserveStartEnd"
              />
              <YAxis 
                stroke="#4a4a6a" 
                tick={{ fontSize: 10, fill: '#888' }}
                tickLine={false}
                domain={['auto', 'auto']}
                label={{
                  value: 'Value',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fill: '#888', fontSize: 10 }
                }}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1a1a2e', 
                  border: '1px solid #2a2a4e',
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
                labelStyle={{ color: '#aaa' }}
                formatter={(value, name) => {
                  // Format numbers nicely
                  if (typeof value === 'number') {
                    return [value.toFixed(2), name];
                  }
                  return [value, name];
                }}
              />
              <Legend 
                wrapperStyle={{ fontSize: '11px', color: '#aaa' }}
                verticalAlign="top"
                height={30}
                formatter={(value, entry) => {
                  // Custom legend formatting
                  const item = validItems.find(i => i.id === entry.dataKey);
                  if (item) {
                    return `${item.country}: ${item.indicator}${item.source ? ` (${item.source})` : ''}`;
                  }
                  return value;
                }}
              />
              {validItems.map(item => (
                <Line
                  key={item.id}
                  type="monotone"
                  dataKey={item.id}
                  name={`${item.country} - ${item.indicator}`}
                  stroke={item.color || '#6bcbff'}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        {/* Footer - List of items with remove buttons */}
        <div className="flex flex-wrap gap-1.5 p-2 border-t border-white/5 shrink-0 max-h-16 overflow-y-auto">
          {validItems.map(item => (
            <span 
              key={item.id}
              className="flex items-center gap-1.5 bg-gray-800/50 text-xs px-2 py-1 rounded-full text-white border border-white/5 hover:bg-gray-700/50 transition-colors"
            >
              <span 
                className="w-2 h-2 rounded-full shrink-0" 
                style={{ background: item.color || '#6bcbff' }} 
              />
              <span className="truncate max-w-32">
                {item.country || 'Unknown'}: {item.indicator ? (item.indicator.length > 15 ? item.indicator.substring(0, 15) + '…' : item.indicator) : 'Unknown'}
              </span>
              {item.source && (
                <span className="text-[8px] text-gray-500 uppercase font-mono">
                  {item.source}
                </span>
              )}
              <button
                onClick={() => removeItem(item.id)}
                className="text-gray-400 hover:text-red-400 ml-0.5 transition-colors"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
