import React, { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, ArrowUpDown, Search } from 'lucide-react';

export default function DataTable({ data = [], columns = [], title }) {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [currentPage, setCurrentPage] = useState(1);
  const [filterText, setFilterText] = useState('');
  const itemsPerPage = 8;

  const filteredData = useMemo(() => {
    return data.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(filterText.toLowerCase())
      )
    );
  }, [data, filterText]);

  const sortedData = useMemo(() => {
    const sortableData = [...filteredData];
    if (sortConfig.key !== null) {
      sortableData.sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableData;
  }, [filteredData, sortConfig]);

  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return sortedData.slice(startIndex, startIndex + itemsPerPage);
  }, [sortedData, currentPage]);

  const totalPages = Math.ceil(sortedData.length / itemsPerPage);

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden my-4 text-xs">
      {title && (
        <div className="px-4 pt-4">
          <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50">{title}</h4>
        </div>
      )}
      <div className="p-3 border-b border-white/10 flex items-center justify-between gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-white/40" />
          <input 
            type="text" 
            placeholder="Search table..." 
            value={filterText}
            onChange={(e) => { setFilterText(e.target.value); setCurrentPage(1); }}
            className="w-full bg-white/5 border-0 rounded-lg pl-7 pr-3 py-1.5 focus:ring-1 focus:ring-white/20 placeholder:text-white/20"
          />
        </div>
        <div className="text-white/40 font-mono">
          {sortedData.length} records
        </div>
      </div>

      <div className="overflow-x-auto pb-1">
        <table className="w-full min-w-max border-collapse">
          <thead>
            <tr className="bg-white/5">
              {columns.map(col => (
                <th 
                  key={col}
                  onClick={() => requestSort(col)}
                  className="px-4 py-2 text-left font-medium text-white/60 border-b border-white/10 cursor-pointer hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    {col}
                    <ArrowUpDown className={`w-3 h-3 ${sortConfig.key === col ? 'text-white' : 'text-white/20'}`} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, i) => (
              <tr key={i} className="hover:bg-white/5 transition-colors border-b border-white/[0.05] last:border-0 text-white/80">
                {columns.map(col => (
                  <td key={col} className="px-4 py-2 font-mono whitespace-nowrap">
                    {typeof row[col] === 'number' ? row[col].toFixed(4) : row[col]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="p-3 border-t border-white/10 flex items-center justify-center gap-2">
          <button 
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(prev => prev - 1)}
            className="p-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-white/40">
            Page {currentPage} of {totalPages}
          </span>
          <button 
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(prev => prev + 1)}
            className="p-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
