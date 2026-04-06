import React, { useState } from 'react';

export default function AdminOverlay({
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
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingWaypoint, setEditingWaypoint] = useState(null); // {gate, runway, index, wp}
  const [editingRunway, setEditingRunway] = useState(null); // {rw}

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
          gate: editingWaypoint.gate,
          runway_id: editingWaypoint.runway,
          index: editingWaypoint.index,
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

      {/* Simulation Speed Section */}
      <div className="section" style={{ marginBottom: '16px' }}>
        <h4>Simulation Speed</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
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
            minWidth: '40px', 
            textAlign: 'right', 
            fontWeight: 'bold', 
            color: '#007bff',
            background: '#e7f3ff',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.8rem'
          }}>
            {activeAirportConfig?.time_scale || 1}x
          </span>
        </div>
      </div>

      {/* Airports Section */}
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
            style={{ width: '100%', background: draftingMode === 'airport' ? '#ffcccc' : '#e7f3ff', color: '#0056b3', borderColor: '#b8daff' }}
            onClick={() => setDraftingMode(draftingMode === 'airport' ? null : 'airport')}
          >
            {draftingMode === 'airport' ? 'Click map for location...' : 'Add Airport (Click map)'}
          </button>
        </div>
      </div>

      {/* Runway Management */}
      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Runways ({activeAirport?.name})</h4>
        <div style={{ maxHeight: '100px', overflowY: 'auto', background: '#f8f9fa', padding: '6px', borderRadius: '6px', border: '1px solid #dee2e6', marginBottom: '10px' }}>
          {activeAirport?.runways?.map(rw => (
            <div key={rw.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 6px', borderBottom: '1px solid #eee', color: '#1a1a1a' }}>
              <span style={{ fontWeight: '500', fontSize: '0.75rem' }}>{rw.id} <span style={{ color: '#6c757d', fontWeight: 'normal' }}>({rw.heading}°)</span></span>
              <div style={{ display: 'flex', gap: '4px' }}>
                <button
                  onClick={() => setEditingRunway({ rw })}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.8rem' }}
                >✏️</button>
                <button
                  onClick={() => {
                    if (window.confirm(`Delete runway ${rw.id}?`)) {
                      sendWSMessage('delete_runway', { airport_code: activeAirport.airport_code, runway_id: rw.id });
                    }
                  }}
                  style={{ background: 'none', border: 'none', color: '#dc3545', cursor: 'pointer', fontWeight: 'bold' }}
                >&times;</button>
              </div>
            </div>
          ))}
        </div>
        <input
          placeholder="New Runway Label..."
          value={runwayLabel}
          onChange={e => setRunwayLabel(e.target.value)}
          style={{ width: '100%', marginBottom: '6px', fontSize: '0.75rem' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', margin: '4px 0', fontSize: '0.7rem' }}>
          <input type="checkbox" id="bidir" checked={isRunwayBidirectional} onChange={e => setIsRunwayBidirectional(e.target.checked)} style={{ width: 'auto', marginRight: '4px' }} />
          <label htmlFor="bidir">Bidirectional</label>
        </div>
        <button
          className="btn"
          disabled={!activeAirport}
          style={{ width: '100%', background: draftingMode === 'runway' ? '#ffcccc' : '#f0f0f0', fontSize: '0.75rem' }}
          onClick={() => setDraftingMode(draftingMode === 'runway' ? null : 'runway')}
        >
          {draftingMode === 'runway' ? 'Set points on map...' : 'Add Runway (Map)'}
        </button>
      </div>

      {/* Pooled Waypoint Dropper */}
      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Waypoint Dropper</h4>
        <button
          className="btn"
          style={{ width: '100%', background: draftingMode === 'waypoint' ? '#ffcccc' : '#e7f3ff', fontSize: '0.75rem' }}
          onClick={() => setDraftingMode(draftingMode === 'waypoint' ? null : 'waypoint')}
        >
          {draftingMode === 'waypoint' ? 'DROPPER ACTIVE (Click Map)' : 'Activate Waypoint Dropper'}
        </button>

        {/* Global Pool List */}
        {activeAirportConfig?.waypoints && Object.keys(activeAirportConfig.waypoints).length > 0 && (
          <div style={{ marginTop: '8px', maxHeight: '100px', overflowY: 'auto', background: '#f8f9fa', borderRadius: '4px', border: '1px solid #eee' }}>
            {Object.values(activeAirportConfig.waypoints).map((wp) => (
              <div key={wp.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem', padding: '4px' }}>
                <span>{wp.name}</span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button onClick={() => setEditingWaypoint({ wp })} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✏️</button>
                  <button
                    onClick={() => sendWSMessage('delete_waypoint', { airport_code: activeAirport.airport_code, waypoint_id: wp.id })}
                    style={{ background: 'none', border: 'none', color: '#dc3545', cursor: 'pointer' }}
                  >&times;</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* STAR Route Builder */}
      <div className="section" style={{ marginTop: '16px' }}>
        <h4>STAR Route Builder</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            <select
              value={starDraft.gate}
              onChange={e => setStarDraft({ ...starDraft, gate: e.target.value })}
              style={{ flex: 1, padding: '4px', fontSize: '0.7rem' }}
            >
              <option value="N">North</option><option value="S">South</option><option value="E">East</option><option value="W">West</option>
            </select>
            <select
              value={starDraft.runway_id || ''}
              onChange={e => setStarDraft({ ...starDraft, runway_id: e.target.value })}
              style={{ flex: 1, padding: '4px', fontSize: '0.7rem' }}
            >
              <option value="">Runway...</option>
              {activeAirport?.runways?.map(rw => <option key={rw.id} value={rw.id}>{rw.id}</option>)}
            </select>
          </div>

          <button
            className="btn"
            disabled={!starDraft.runway_id}
            style={{ width: '100%', background: draftingMode === 'route' ? '#ffcccc' : '#e7f3ff', fontSize: '0.75rem', fontWeight: 'bold' }}
            onClick={() => setDraftingMode(draftingMode === 'route' ? null : 'route')}
          >
            {draftingMode === 'route' ? 'Click Dots on Map...' : 'Start Route Builder'}
          </button>

          {draftingMode === 'route' && (
            <div style={{ padding: '6px', background: '#fff9e6', border: '1px solid #ffeeba', borderRadius: '4px', fontSize: '0.7rem' }}>
              <strong>Sequence:</strong> {starDraft.sequence.length > 0 ? starDraft.sequence.map(id => activeAirportConfig.waypoints[id]?.name || id).join(' → ') : 'No points selected'}
              <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                <button onClick={() => setStarDraft({ ...starDraft, sequence: [] })} className="btn" style={{ flex: 1 }}>Clear</button>
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
                  style={{ flex: 1, background: '#007bff' }}
                >Save Route</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Spawn Section */}
      <div className="section" style={{ marginTop: '16px' }}>
        <h4>Spawn</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <input placeholder="Callsign" value={spawnFields.callsign} onChange={e => setSpawnFields({ ...spawnFields, callsign: e.target.value })} style={{ width: '100%', fontSize: '0.75rem' }} />
          <div style={{ display: 'flex', gap: '4px' }}>
            <select 
              value={spawnFields.gate} 
              onChange={e => setSpawnFields({ ...spawnFields, gate: e.target.value })} 
              style={{ flex: 1, fontSize: '0.75rem', padding: '2px' }}
            >
              {activeAirportConfig?.gates ? 
                Object.keys(activeAirportConfig.gates).map(g => <option key={g} value={g}>{g}</option>) :
                <><option value="N">N</option><option value="S">S</option><option value="E">E</option><option value="W">W</option></>
              }
            </select>
            <input type="number" placeholder="Alt" value={spawnFields.altitude} onChange={e => setSpawnFields({ ...spawnFields, altitude: e.target.value })} style={{ flex: 1, fontSize: '0.75rem' }} />
            <input type="number" placeholder="Spd" value={spawnFields.speed} onChange={e => setSpawnFields({ ...spawnFields, speed: e.target.value })} style={{ flex: 1, fontSize: '0.75rem' }} />
          </div>
          <button onClick={handleSpawn} className="btn btn-primary" style={{ background: '#28a745', color: 'white', border: 'none', padding: '6px', fontSize: '0.75rem' }}>Spawn</button>
        </div>
      </div>

      <div className="section" style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
        <button
          className="btn"
          style={{ flex: 1, background: '#f8f9fa', color: '#dc3545', fontSize: '0.75rem', fontWeight: 'bold' }}
          onClick={() => sendWSMessage('reset', {})}
        >
          Reset
        </button>
        <button
          className="btn"
          style={{ flex: 1, background: '#dc3545', color: '#fff', fontSize: '0.75rem', fontWeight: 'bold', border: 'none' }}
          onClick={() => {
            if (window.confirm("Are you sure you want to SHUT DOWN the server?")) {
              sendWSMessage('shutdown', {});
            }
          }}
        >
          Stop Server
        </button>
      </div>

      {renderEditModal()}

      <style>{`
        .admin-overlay {
          position: absolute; top: 15px; right: 50px; z-index: 1000;
          background: #fff; border: 1px solid #dee2e6; padding: 12px;
          width: 240px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
          font-family: inherit; border-radius: 8px; max-height: 90vh; overflow-y: auto;
        }
        .admin-overlay h4 { margin: 0 0 8px 0; font-size: 0.7rem; color: #666; text-transform: uppercase; font-weight: bold; }
        .admin-overlay .section { padding-top: 8px; margin-top: 8px; border-top: 1px solid #eee; }
        .btn { cursor: pointer; border-radius: 4px; border: 1px solid #ced4da; padding: 4px 8px; font-size: 0.75rem; background: #fff; }
        .btn-primary { background: #007bff; color: #fff; border-color: #007bff; }
      `}</style>
    </div>
  );
}
