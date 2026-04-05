import React, { useState } from 'react';

export default function AdminOverlay({ 
  airports = [], 
  activeAirport, 
  onSelectAirport, 
  onCreateAirport,
  onCreateRunway,
  isDraftingAirport,
  setIsDraftingAirport,
  airportName,
  setAirportName,
  isDraftingRunway,
  setIsDraftingRunway,
  isRunwayBidirectional,
  setIsRunwayBidirectional
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [runwayLabel, setRunwayLabel] = useState("");

  if (!isExpanded) {
    return (
      <button 
        onClick={() => setIsExpanded(true)}
        className="btn"
        style={{ 
          position: 'absolute', 
          top: '10px', 
          right: '10px', 
          zIndex: 1000, 
          background: 'rgba(255,255,255,0.8)', 
          border: '1px solid #999',
          padding: '4px 8px',
          fontSize: '0.75rem',
          borderRadius: '4px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}
      >
        Admin Tools 🛠️
      </button>
    );
  }

  return (
    <div className="admin-overlay">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong>Admin Tools</strong>
        <button onClick={() => setIsExpanded(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>&times;</button>
      </div>

      <div className="section">
        <h4>Airports</h4>
        <div style={{ maxHeight: '100px', overflowY: 'auto', border: '1px solid #eee', padding: '4px' }}>
          {airports.map(ap => (
            <div 
              key={ap.name} 
              onClick={() => onSelectAirport(ap)}
              style={{ padding: '4px', cursor: 'pointer', background: activeAirport?.name === ap.name ? '#eef' : 'none' }}
            >
              {ap.name}
            </div>
          ))}
        </div>
        
        <div style={{ marginTop: '8px' }}>
          <input 
            placeholder="New name..." 
            value={airportName} 
            onChange={e => setAirportName(e.target.value)} 
            style={{ width: '100%', marginBottom: '4px' }}
          />
          <button 
            className="btn" 
            style={{ width: '100%', background: isDraftingAirport ? '#ffaaaa' : '#99ff99' }}
            onClick={() => setIsDraftingAirport(!isDraftingAirport)}
          >
            {isDraftingAirport ? 'Click map for location...' : 'Add Airport (Click map)'}
          </button>
        </div>
      </div>

      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Runways ({activeAirport?.name})</h4>
        <input 
           placeholder="Runway Label (e.g. 09L)..." 
           value={runwayLabel} 
           onChange={e => setRunwayLabel(e.target.value)} 
           style={{ width: '100%', marginBottom: '4px' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', margin: '4px 0' }}>
          <input 
            type="checkbox" 
            id="bidir" 
            checked={isRunwayBidirectional} 
            onChange={e => setIsRunwayBidirectional(e.target.checked)} 
            style={{ width: 'auto', margin: '0 4px 0 0' }}
          />
          <label htmlFor="bidir">Bi-directional</label>
        </div>
        <button 
          className="btn" 
          disabled={!activeAirport}
          style={{ width: '100%', background: isDraftingRunway ? '#ffaaaa' : '#99ccff' }}
          onClick={() => setIsDraftingRunway(!isDraftingRunway)}
        >
          {isDraftingRunway ? 'Set points on map...' : 'Add Runway (Set points)'}
        </button>
      </div>

      <style>{`
        .admin-overlay {
          position: absolute;
          top: 10px;
          right: 50px;
          z-index: 1000;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(4px);
          color: white;
          border: 1px solid rgba(255,255,255,0.2);
          padding: 8px;
          min-width: 140px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.3);
          font-size: 0.75rem;
          border-radius: 6px;
        }
        .admin-overlay h4 {
          margin: 4px 0 2px 0;
          font-size: 0.8rem;
          color: #aaa;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .admin-overlay .section {
          padding-top: 4px;
          margin-top: 6px;
          border-top: 1px solid rgba(255,255,255,0.1);
        }
        .admin-overlay .btn {
          font-size: 0.7rem;
          padding: 4px 8px;
          margin-top: 4px;
          background: #444;
          color: #eee;
          border: none;
          border-radius: 3px;
          cursor: pointer;
          transition: background 0.2s;
        }
        .admin-overlay .btn:hover {
          background: #555;
        }
        .admin-overlay input {
          font-size: 0.7rem;
          padding: 3px;
          background: #222;
          border: 1px solid #444;
          color: white;
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
}
