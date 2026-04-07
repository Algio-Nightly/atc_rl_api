import React, { useState } from 'react';

export default function AdminPanel({
  gameState,
  airports = [],
  activeAirport,
  activeAirportConfig,
  onSelectAirport,
  sendWSMessage,
  draftingMode,
  setDraftingMode,
  airportName,
  setAirportName,
  isRunwayBidirectional,
  setIsRunwayBidirectional,
  starDraft,
  setStarDraft
}) {
  const [editingWaypoint, setEditingWaypoint] = useState(null); // {gate, runway, index, wp}
  const [editingRunway, setEditingRunway] = useState(null); // {rw}

  const [runwayLabel, setRunwayLabel] = useState("");
  const [spawnFields, setSpawnFields] = useState({
    callsign: `UA${Math.floor(Math.random() * 900) + 100}`,
    type: "B738",
    altitude: 10000,
    speed: 250,
    gate: "N",
    isDeparture: false,
    runwayId: "",
    terminalGateId: ""
  });

  const handleSpawn = () => {
    sendWSMessage('spawn', {
      ...spawnFields,
      is_departure: spawnFields.isDeparture,
      runway_id: spawnFields.runwayId,
      terminal_gate_id: spawnFields.terminalGateId,
      altitude: parseInt(spawnFields.altitude || 0),
      speed: parseInt(spawnFields.speed || 0)
    });
    setSpawnFields(prev => ({
      ...prev,
      callsign: `UA${Math.floor(Math.random() * 900) + 100}`
    }));
  };

  const renderEditModal = () => {
    if (!editingWaypoint && !editingRunway) return null;

    const isWaypoint = !!editingWaypoint;
    const title = isWaypoint ? `Edit Waypoint: ${editingWaypoint.wp.name}` : `Edit Runway: ${editingRunway.rw.id}`;

    const handleSave = (e) => {
      e.preventDefault();
      const formData = new FormData(e.target);

      if (isWaypoint) {
        sendWSMessage('update_waypoint', {
          airport_code: activeAirport.airport_code,
          waypoint_id: editingWaypoint.wp.id,
          name: formData.get('name'),
          target_alt: parseInt(formData.get('alt')),
          target_speed: parseInt(formData.get('speed'))
        });
        setEditingWaypoint(null);
      } else {
        sendWSMessage('update_runway', {
          airport_code: activeAirport.airport_code,
          runway_id: editingRunway.rw.id,
          new_id: formData.get('id'),
          heading: parseFloat(formData.get('heading'))
        });
        setEditingRunway(null);
      }
    };

    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 3000,
        display: 'flex', justifyContent: 'center', alignItems: 'center'
      }}>
        <div style={{
          background: 'white', padding: '20px', borderRadius: '8px',
          width: '300px', boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
        }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem', color: '#1a1a1a' }}>{title}</h3>
          <form onSubmit={handleSave}>
            {isWaypoint ? (
              <>
                <div style={{ marginBottom: '10px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#666' }}>Name</label>
                  <input name="name" defaultValue={editingWaypoint.wp.name} style={{ width: '100%', padding: '4px' }} />
                </div>
                <div style={{ marginBottom: '10px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#666' }}>Target Altitude (ft)</label>
                  <input name="alt" type="number" defaultValue={editingWaypoint.wp.target_alt} style={{ width: '100%', padding: '4px' }} />
                </div>
                <div style={{ marginBottom: '15px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#666' }}>Target Speed (kts)</label>
                  <input name="speed" type="number" defaultValue={editingWaypoint.wp.target_speed} style={{ width: '100%', padding: '4px' }} />
                </div>
              </>
            ) : (
              <>
                <div style={{ marginBottom: '10px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#666' }}>Runway ID</label>
                  <input name="id" defaultValue={editingRunway.rw.id} style={{ width: '100%', padding: '4px' }} />
                </div>
                <div style={{ marginBottom: '15px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#666' }}>Heading (°)</label>
                  <input name="heading" type="number" step="0.1" defaultValue={editingRunway.rw.heading} style={{ width: '100%', padding: '4px' }} />
                </div>
              </>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" onClick={() => { setEditingWaypoint(null); setEditingRunway(null); }} className="btn btn-outline" style={{ padding: '4px 12px' }}>Cancel</button>
              <button type="submit" className="btn btn-primary" style={{ padding: '4px 12px', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px' }}>Save</button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  return (
    <nav className="admin-panel thin-scroll">
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ color: '#555', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 'bold' }}>Admin Control</h2>
      </div>

      {/* Simulation Speed Section */}
      <div className="section" style={{ marginBottom: '16px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Sim Scale</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input 
            type="range" 
            min="1" 
            max="8" 
            step="1"
            value={activeAirportConfig?.time_scale || 1}
            onChange={(e) => sendWSMessage('set_time_scale', { scale: e.target.value })}
            style={{ 
              flex: 1,
              cursor: 'pointer',
              accentColor: '#007bff'
            }}
          />
          <span style={{ 
            minWidth: '35px', 
            textAlign: 'right', 
            fontWeight: 'bold', 
            color: '#007bff',
            fontSize: '0.8rem'
          }}>
            {activeAirportConfig?.time_scale || 1}x
          </span>
        </div>
      </div>

      {/* Airports Section */}
      <div className="section" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Airports</h4>
        <div style={{ maxHeight: '80px', overflowY: 'auto', border: '1px solid #eee', padding: '4px', borderRadius: '4px', background: '#fafafa', marginBottom: '8px' }}>
          {airports.map(ap => (
            <div
              key={ap.name}
              onClick={() => onSelectAirport(ap)}
              style={{
                padding: '4px 8px',
                cursor: 'pointer',
                fontSize: '0.7rem',
                borderRadius: '3px',
                marginBottom: '2px',
                background: activeAirport?.name === ap.name ? '#007bff' : 'none',
                color: activeAirport?.name === ap.name ? '#fff' : '#444'
              }}
            >
              {ap.name}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '4px' }}>
          <input
            placeholder="New..."
            value={airportName}
            onChange={e => setAirportName(e.target.value)}
            style={{ flex: 1, padding: '4px', fontSize: '0.7rem', border: '1px solid #eee', borderRadius: '4px' }}
          />
          <button
            className="btn"
            style={{ 
              padding: '4px 8px', 
              fontSize: '0.65rem',
              background: draftingMode === 'airport' ? '#ffcccc' : '#e7f3ff', 
              color: '#0056b3'
            }}
            onClick={() => setDraftingMode(draftingMode === 'airport' ? null : 'airport')}
          >
            {draftingMode === 'airport' ? '📍' : 'Add'}
          </button>
        </div>
      </div>

      {/* Runway Management */}
      <div className="section" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Runways ({activeAirport?.name})</h4>
        <div style={{ maxHeight: '120px', overflowY: 'auto', background: '#fafafa', padding: '4px', borderRadius: '4px', border: '1px solid #eee', marginBottom: '8px' }}>
          {activeAirport?.runways?.map(rw => {
            const statusObj = gameState?.runway_status?.[rw.id];
            const status = statusObj?.status || "CLEAR";
            
            let statusColor = "#6c757d"; // Clear
            let statusText = "CLEAR";
            
            if (status === "OCCUPIED") {
              statusColor = "#dc3545"; // Red
              statusText = statusObj.occupied_by;
            } else if (status === "RESERVED") {
              statusColor = "#007bff"; // Blue
              statusText = `Reserved: ${statusObj.reserved_by}`;
            } else if (status === "COOLDOWN") {
              statusColor = "#ffc107"; // Amber
              statusText = `Cooling: ${statusObj.cooldown_remaining}s`;
            }

            return (
              <div key={rw.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 4px', borderBottom: '1px solid #f0f0f0', color: '#444' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 'bold' }}>{rw.heading.toFixed(0).padStart(2, '0')} [{rw.id}]</span>
                  <span style={{ 
                    fontSize: '0.55rem', 
                    color: status === "CLEAR" ? "#28a745" : "white", 
                    background: status === "CLEAR" ? "none" : statusColor,
                    padding: status === "CLEAR" ? "0" : "1px 4px",
                    borderRadius: '2px',
                    fontWeight: 'bold',
                    width: 'fit-content'
                  }}>
                    {statusText}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button onClick={() => setEditingRunway({ rw })} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.7rem' }}>✏️</button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete runway ${rw.id}?`)) {
                        sendWSMessage('delete_runway', { airport_code: activeAirport.airport_code, runway_id: rw.id });
                      }
                    }}
                    style={{ background: 'none', border: 'none', color: '#dc3545', cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}
                  >&times;</button>
                </div>
              </div>
            );
          })}
        </div>
        <button
          className="btn"
          disabled={!activeAirport}
          style={{ width: '100%', background: draftingMode === 'runway' ? '#ffcccc' : '#f8f9fa', fontSize: '0.65rem' }}
          onClick={() => setDraftingMode(draftingMode === 'runway' ? null : 'runway')}
        >
          {draftingMode === 'runway' ? 'Click Map...' : 'Add Runway'}
        </button>
      </div>

      {/* Pooled Waypoint Dropper */}
      <div className="section" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Waypoints</h4>
        <button
          className="btn"
          style={{ width: '100%', background: draftingMode === 'waypoint' ? '#ffcccc' : '#e7f3ff', fontSize: '0.65rem', marginBottom: '8px' }}
          onClick={() => setDraftingMode(draftingMode === 'waypoint' ? null : 'waypoint')}
        >
          {draftingMode === 'waypoint' ? 'Drop Active...' : 'Activate Dropper'}
        </button>

        {activeAirportConfig?.waypoints && Object.keys(activeAirportConfig.waypoints).length > 0 && (
          <div style={{ maxHeight: '80px', overflowY: 'auto', background: '#fafafa', borderRadius: '4px', border: '1px solid #eee' }}>
            {Object.values(activeAirportConfig.waypoints).map((wp) => (
              <div key={wp.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.6rem', padding: '2px 6px', borderBottom: '1px solid #f9f9f9' }}>
                <span>{wp.name}</span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button onClick={() => setEditingWaypoint({ wp })} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.65rem' }}>✏️</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* STAR Route Builder */}
      <div className="section" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Arrival Routes</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            <select
              value={starDraft.gate}
              onChange={e => setStarDraft({ ...starDraft, gate: e.target.value })}
              style={{ flex: 1, padding: '2px', fontSize: '0.65rem', border: '1px solid #eee' }}
            >
              {activeAirportConfig?.gates ? 
                Object.keys(activeAirportConfig.gates).map(g => <option key={g} value={g}>{g}</option>) :
                <><option value="N">N</option><option value="S">S</option><option value="E">E</option><option value="W">W</option></>
              }
            </select>
            <select
              value={starDraft.runway_id || ''}
              onChange={e => setStarDraft({ ...starDraft, runway_id: e.target.value })}
              style={{ flex: 1, padding: '2px', fontSize: '0.65rem', border: '1px solid #eee' }}
            >
              <option value="">RWY...</option>
              {activeAirport?.runways?.map(rw => <option key={rw.id} value={rw.id}>{rw.id}</option>)}
            </select>
          </div>

          <button
            className="btn"
            disabled={!starDraft.runway_id}
            style={{ width: '100%', background: draftingMode === 'route' ? '#ffcccc' : '#f8f9fa', fontSize: '0.65rem' }}
            onClick={() => setDraftingMode(draftingMode === 'route' ? null : 'route')}
          >
            {draftingMode === 'route' ? 'Building...' : 'Build Route'}
          </button>

          {draftingMode === 'route' && (
            <div style={{ padding: '6px', background: '#fff9e6', border: '1px solid #ffeeba', borderRadius: '4px', marginTop: '4px' }}>
              <select 
                value="" 
                onChange={(e) => setStarDraft(prev => ({ ...prev, sequence: [...prev.sequence, e.target.value] }))} 
                style={{ width: '100%', padding: '2px', fontSize: '0.65rem', marginBottom: '6px' }}
              >
                <option value="">Add Waypoint...</option>
                {Object.values(activeAirportConfig?.waypoints || {})
                  .sort((a,b) => a.name.localeCompare(b.name))
                  .map(wp => <option key={wp.id} value={wp.id}>{wp.name}</option>)}
              </select>
              
              <div style={{ fontSize: '0.6rem', marginBottom: '6px', color: '#666', maxHeight: '40px', overflowY: 'auto' }}>
                {starDraft.sequence.map(id => activeAirportConfig.waypoints[id]?.name || id).join(' → ')}
              </div>

              <div style={{ display: 'flex', gap: '4px' }}>
                <button onClick={() => setStarDraft({ ...starDraft, sequence: [] })} className="btn" style={{ flex: 1, fontSize: '0.6rem', padding: '2px' }}>Clear</button>
                <button 
                  disabled={starDraft.sequence.length === 0}
                  onClick={() => {
                    sendWSMessage('save_star_route', {
                      airport_code: activeAirport.airport_code,
                      gate: starDraft.gate,
                      runway_id: starDraft.runway_id,
                      sequence: starDraft.sequence
                    });
                    setDraftingMode(null);
                    setStarDraft(prev => ({ ...prev, sequence: [] }));
                  }}
                  className="btn btn-primary"
                  style={{ flex: 1, background: '#007bff', fontSize: '0.6rem', padding: '2px' }}
                >Save</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Spawn Section */}
      <div className="section" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', fontWeight: 'bold' }}>Spawn Aircraft</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <input 
            placeholder="Callsign" 
            value={spawnFields.callsign} 
            onChange={e => setSpawnFields({ ...spawnFields, callsign: e.target.value })} 
            style={{ padding: '6px', fontSize: '0.7rem', border: '1px solid #eee', borderRadius: '4px' }} 
          />
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <label style={{ fontSize: '0.65rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={spawnFields.isDeparture} 
                onChange={e => setSpawnFields({ ...spawnFields, isDeparture: e.target.checked })} 
              />
              Departure
            </label>
            {spawnFields.isDeparture && (
              <select 
                value={spawnFields.runwayId} 
                onChange={e => setSpawnFields({ ...spawnFields, runwayId: e.target.value })} 
                style={{ flex: 1, fontSize: '0.65rem', padding: '4px', border: '1px solid #eee' }}
              >
                <option value="">Select Runway...</option>
                {activeAirport?.runways?.map(rw => <option key={rw.id} value={rw.id}>{rw.id}</option>)}
              </select>
            )}
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            {/* Case 1: Arrival (Always show Entry Gate) */}
            {!spawnFields.isDeparture && (
              <select 
                value={spawnFields.gate} 
                onChange={e => setSpawnFields({ ...spawnFields, gate: e.target.value })} 
                style={{ flex: 1, fontSize: '0.65rem', padding: '4px', border: '1px solid #eee' }}
              >
                <option value="" disabled>Entry Gate</option>
                {activeAirportConfig?.gates ? 
                  Object.keys(activeAirportConfig.gates).map(g => <option key={g} value={g}>{g}</option>) :
                  <><option value="N">N</option><option value="S">S</option><option value="E">E</option><option value="W">W</option></>
                }
              </select>
            )}

            {/* Case 2: Departure (Show BOTH Exit Gate and Terminal Stand) */}
            {spawnFields.isDeparture && (
              <>
                <select 
                  value={spawnFields.gate} 
                  onChange={e => setSpawnFields({ ...spawnFields, gate: e.target.value })} 
                  style={{ flex: 1, fontSize: '0.65rem', padding: '4px', border: '1px solid #eee' }}
                >
                  <option value="" disabled>Exit Gate</option>
                  {activeAirportConfig?.gates ? 
                    Object.keys(activeAirportConfig.gates).map(g => <option key={g} value={g}>{g}</option>) :
                    <><option value="N">N</option><option value="S">S</option><option value="E">E</option><option value="W">W</option></>
                  }
                </select>
                <select 
                  value={spawnFields.terminalGateId} 
                  onChange={e => setSpawnFields({ ...spawnFields, terminalGateId: e.target.value })} 
                  style={{ flex: 1, fontSize: '0.65rem', padding: '4px', border: '1px solid #eee', background: '#f0f4ff' }}
                >
                  <option value="">Threshold (Direct)</option>
                  {activeAirportConfig?.terminal_gates && 
                    Object.keys(activeAirportConfig.terminal_gates).map(g => (
                      <option key={g} value={g}>Stand: {g}</option>
                    ))
                  }
                </select>
              </>
            )}

            {!spawnFields.isDeparture && (
              <>
                <input type="number" placeholder="Alt" value={spawnFields.altitude} onChange={e => setSpawnFields({ ...spawnFields, altitude: e.target.value })} style={{ flex: 1, padding: '4px', fontSize: '0.65rem', border: '1px solid #eee' }} />
                <input type="number" placeholder="Spd" value={spawnFields.speed} onChange={e => setSpawnFields({ ...spawnFields, speed: e.target.value })} style={{ flex: 1, padding: '4px', fontSize: '0.65rem', border: '1px solid #eee' }} />
              </>
            )}
          </div>
          <button onClick={handleSpawn} className="btn btn-primary" style={{ background: '#28a745', color: 'white', border: 'none', padding: '8px', fontSize: '0.7rem' }}>Spawn Flight</button>
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: '16px', display: 'flex', gap: '4px' }}>
        <button className="btn" style={{ flex: 1, fontSize: '0.65rem', color: '#dc3545' }} onClick={() => sendWSMessage('reset', {})}>Reset</button>
        <button 
          className="btn" 
          style={{ flex: 1, fontSize: '0.65rem', background: '#dc3545', color: '#fff', border: 'none' }} 
          onClick={() => {
            if (window.confirm("Shut down server?")) sendWSMessage('shutdown', {});
          }}
        >Stop</button>
      </div>

      {renderEditModal()}

      <style>{`
        .admin-panel {
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        .thin-scroll::-webkit-scrollbar { width: 4px; }
        .thin-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .thin-scroll::-webkit-scrollbar-thumb { background: #ccc; border-radius: 10px; }
      `}</style>
    </nav>
  );
}
