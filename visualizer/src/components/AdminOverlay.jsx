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
  setIsRunwayBidirectional,
  sendWSMessage
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [runwayLabel, setRunwayLabel] = useState("");
  const [spawnFields, setSpawnFields] = useState({
    callsign: `UA${Math.floor(Math.random() * 900) + 100}`,
    type: "B738",
    altitude: 10000,
    speed: 250,
    gate: "N"
  });

  const handleSpawn = () => {
    sendWSMessage('spawn', { 
      gate: spawnFields.gate,
      callsign: spawnFields.callsign,
      type: spawnFields.type,
      altitude: parseInt(spawnFields.altitude),
      speed: parseInt(spawnFields.speed)
    });
    // Generate new random callsign for next use
    setSpawnFields(prev => ({ 
      ...prev, 
      callsign: `UA${Math.floor(Math.random() * 900) + 100}` 
    }));
  };

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
        Admin Tools
      </button>
    );
  }

  return (
    <div className="admin-overlay">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <strong style={{ color: '#1a1a1a', fontSize: '0.85rem' }}>Admin Tools</strong>
        <button onClick={() => setIsExpanded(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#666', fontSize: '1.2rem' }}>&times;</button>
      </div>

      <div className="section">
        <h4>Airports</h4>
        <div style={{ maxHeight: '100px', overflowY: 'auto', border: '1px solid #dee2e6', padding: '4px', borderRadius: '4px', background: '#f8f9fa' }}>
          {airports.map(ap => (
            <div 
              key={ap.name} 
              onClick={() => onSelectAirport(ap)}
              style={{ 
                padding: '6px', 
                cursor: 'pointer', 
                fontSize: '0.75rem',
                borderRadius: '4px',
                marginBottom: '2px',
                background: activeAirport?.name === ap.name ? '#007bff' : 'none',
                color: activeAirport?.name === ap.name ? '#fff' : '#1a1a1a'
              }}
            >
              {ap.name}
            </div>
          ))}
        </div>
        
        <div style={{ marginTop: '10px' }}>
          <input 
            placeholder="New name..." 
            value={airportName} 
            onChange={e => setAirportName(e.target.value)} 
            style={{ width: '100%', marginBottom: '6px' }}
          />
          <button 
            className="btn" 
            style={{ width: '100%', background: isDraftingAirport ? '#ffcccc' : '#e7f3ff', color: '#0056b3', borderColor: '#b8daff' }}
            onClick={() => setIsDraftingAirport(!isDraftingAirport)}
          >
            {isDraftingAirport ? 'Click map for location...' : 'Add Airport (Click map)'}
          </button>
        </div>
      </div>

      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Runway Management ({activeAirport?.name})</h4>
        <div style={{ maxHeight: '100px', overflowY: 'auto', background: '#f8f9fa', padding: '6px', borderRadius: '6px', border: '1px solid #dee2e6', marginBottom: '10px' }}>
          {activeAirport?.runways?.map(rw => (
            <div key={rw.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 6px', borderBottom: '1px solid #eee', color: '#1a1a1a' }}>
              <span style={{ fontWeight: '500' }}>{rw.id} <span style={{ color: '#6c757d', fontWeight: 'normal' }}>({rw.heading}°)</span></span>
              <button 
                onClick={() => {
                  if (window.confirm(`Delete runway ${rw.id}?`)) {
                    sendWSMessage('delete_runway', { airport_name: activeAirport.name, runway_id: rw.id });
                  }
                }}
                style={{ background: 'none', border: 'none', color: '#dc3545', cursor: 'pointer', fontWeight: 'bold' }}
              >×</button>
            </div>
          ))}
          {(!activeAirport?.runways || activeAirport.runways.length === 0) && <div style={{ color: '#6c757d', fontSize: '0.7rem' }}>No runways defined.</div>}
        </div>

        <input 
           placeholder="Runway Label (e.g. 09L)..." 
           value={runwayLabel} 
           onChange={e => setRunwayLabel(e.target.value)} 
           style={{ width: '100%', marginBottom: '6px' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', margin: '6px 0', fontSize: '0.75rem', color: '#495057' }}>
          <input 
            type="checkbox" 
            id="bidir" 
            checked={isRunwayBidirectional} 
            onChange={e => setIsRunwayBidirectional(e.target.checked)} 
            style={{ width: 'auto', margin: '0 6px 0 0' }}
          />
          <label htmlFor="bidir">Bi-directional</label>
        </div>
        <button 
          className="btn" 
          disabled={!activeAirport}
          style={{ width: '100%', background: isDraftingRunway ? '#ffcccc' : '#f0f0f0', color: '#1a1a1a' }}
          onClick={() => setIsDraftingRunway(!isDraftingRunway)}
        >
          {isDraftingRunway ? 'Set points on map...' : 'Add Runway (Set points)'}
        </button>
      </div>

      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Quick Spawn</h4>
        <div style={{ display: 'flex', gap: '6px' }}>
          {['N', 'S', 'E', 'W'].map(gate => (
            <button 
              key={gate}
              className="btn"
              style={{ flex: 1, padding: '4px 0' }}
              onClick={() => sendWSMessage('spawn', { gate })}
            >
              {gate}
            </button>
          ))}
        </div>
      </div>

      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Custom Spawn</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', gap: '6px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.65rem', color: '#6c757d', marginBottom: '2px', display: 'block' }}>Callsign</label>
              <input 
                placeholder="Callsign" 
                value={spawnFields.callsign} 
                onChange={e => setSpawnFields({...spawnFields, callsign: e.target.value})}
                style={{ width: '100%' }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.65rem', color: '#6c757d', marginBottom: '2px', display: 'block' }}>Type</label>
              <input 
                placeholder="Type" 
                value={spawnFields.type} 
                onChange={e => setSpawnFields({...spawnFields, type: e.target.value})}
                style={{ width: '100%' }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.65rem', color: '#6c757d', marginBottom: '2px', display: 'block' }}>Altitude (ft)</label>
              <input 
                type="number"
                value={spawnFields.altitude} 
                onChange={e => setSpawnFields({...spawnFields, altitude: e.target.value})}
                style={{ width: '100%' }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.65rem', color: '#6c757d', marginBottom: '2px', display: 'block' }}>Speed (kts)</label>
              <input 
                type="number"
                value={spawnFields.speed} 
                onChange={e => setSpawnFields({...spawnFields, speed: e.target.value})}
                style={{ width: '100%' }}
              />
            </div>
          </div>
          <div>
            <label style={{ fontSize: '0.65rem', color: '#6c757d', marginBottom: '2px', display: 'block' }}>Gate</label>
            <select 
              value={spawnFields.gate} 
              onChange={e => setSpawnFields({...spawnFields, gate: e.target.value})}
              style={{ width: '100%', background: '#fff', color: '#1a1a1a', fontSize: '0.75rem', border: '1px solid #ced4da', borderRadius: '4px', padding: '4px' }}
            >
              <option value="N">North Gate</option>
              <option value="S">South Gate</option>
              <option value="E">East Gate</option>
              <option value="W">West Gate</option>
            </select>
          </div>
          <button 
            className="btn" 
            style={{ background: '#28a745', color: 'white', marginTop: '10px', border: 'none' }}
            onClick={handleSpawn}
          >
            Spawn Aircraft
          </button>
        </div>
      </div>

      <div className="section" style={{ marginTop: '16px' }}>
        <button 
          className="btn" 
          style={{ width: '100%', background: '#f8f9fa', color: '#dc3545', fontWeight: 'bold' }}
          onClick={() => {
            if (window.confirm("Are you sure you want to reset the simulation? All aircraft will be removed.")) {
              sendWSMessage('reset', {});
            }
          }}
        >
          Reset Simulation
        </button>
      </div>

      <style>{`
        .admin-overlay {
          position: absolute;
          top: 15px;
          right: 50px;
          z-index: 1000;
          background: #ffffff;
          color: #1a1a1a;
          border: 1px solid #dee2e6;
          padding: 16px;
          width: 260px;
          box-shadow: 0 10px 40px rgba(0,0,0,0.1);
          font-size: 0.8rem;
          border-radius: 12px;
          max-height: 85vh;
          overflow-y: auto;
        }
        .admin-overlay h4 {
          margin: 0 0 10px 0;
          font-size: 0.75rem;
          color: #495057;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          font-weight: 700;
        }
        .admin-overlay .section {
          padding-top: 12px;
          margin-top: 12px;
          border-top: 1px solid #f1f3f5;
        }
        .admin-overlay input {
          font-size: 0.75rem;
          padding: 6px 8px;
          background: #ffffff;
          border: 1px solid #ced4da;
          color: #1a1a1a;
          border-radius: 4px;
          transition: border-color 0.2s;
        }
        .admin-overlay input:focus {
          border-color: #80bdff;
          outline: none;
          box-shadow: 0 0 0 0.2rem rgba(0,123,255,.1);
        }
      `}</style>
    </div>
  );
}
